# 저신뢰 영역 검증 전략 — Round 12

v70 검증(R11) 결과를 바탕으로 여전히 신뢰도가 낮거나 미검증된 영역의 **근본 원인과 개선 전략**을 기술합니다.

---

## 1. 신분 변경(status_change) — 자연어 전환 표현 미감지

### 1-1. 현상

| 입력 예시 | 예상 경로 | 실측 경로 |
|---|---|---|
| `학생비자를 취업비자로 바꾸고 싶어요` | EXC/status_change | RESP (기본 취업 비자 안내) |
| `현재 비자 종류를 조정하려면 어떻게 해요?` | EXC/status_change | RESP 또는 GENERAL |
| `지금 비자에서 다른 걸로 전환하고 싶은데` | EXC/status_change | 불확실 |

### 1-2. 근본 원인

`domain.py`의 `EXCEPTION_KEYWORDS`는 명사형 키워드("비자 전환", "신분 변경")를 커버하지만,
**동사형 자연어 표현**("바꾸고 싶어요", "조정하려면", "갈아타고 싶어요")을 감지하지 못한다.

또한 국가 없이 순수하게 **현재 비자 유형 → 목표 비자 유형** 형식으로만 질문하면
`detect_country()`가 null을 반환하여 `intent_classifier`가 정보 부족으로 general_chat 분기를 택한다.

### 1-3. 개선 전략

**A. `domain.py` EXCEPTION_KEYWORDS 보강:**
```python
"바꾸고 싶": "status_change",
"바꾸려면":  "status_change",
"갈아타고":  "status_change",
"전환하고 싶": "status_change",
"유형을 바꾸": "status_change",
"종류를 바꾸": "status_change",
```

**B. `intent.py` arrow regex 확장:**

현재 `_ARROW_STATUS_CHANGE_RE`는 `→` 및 `->` 기호만 처리.
한국어 "에서 ~ 로" / "를 ~ 로" 패턴을 추가:
```python
_ARROW_STATUS_CHANGE_RE = re.compile(
    r"(관광|여행|학생|유학|취업|워킹홀리데이|워홀|취업비자|학생비자|관광비자)"
    r"(?:\s*[→\->]\s*|\s*(?:에서|를|을)\s*)"  # ← 확장
    r"(취업|영주|영주권|유학|워킹홀리데이|정착|이민)",
    re.IGNORECASE
)
```

**C. 국가 없는 status_change 처리:**

`detected_exception == "status_change"` 이면 country=None이어도 exception_handler로 라우팅.
(현재는 country가 없으면 일반 RESP로 폴백하는 경우가 있음)

### 1-4. 검증 케이스 (→ `scenarios_low_confidence.py` Group 1)
- 명시적 국가 + 동사형 전환 표현
- 국가 없이 + 비자 유형 전환 표현
- 국가 맥락이 이전 턴에서만 있는 경우 (implicit country)
- "바꾸고 싶다" 단독 vs "비자를 바꾸고 싶다"

---

## 2. G2_EXC 기타 예외 — 미등록 예외 유형 누락

### 2-1. 현상

| 입력 예시 | 예상 경로 | 실측 경로 |
|---|---|---|
| `독일에서 난민 신청은 어떻게 하나요?` | EXC/cross_rule | RESP (취업 안내로 오분류) |
| `정치적 망명 절차가 궁금해요` | EXC/cross_rule | GENERAL |
| `과거에 경범죄 기록이 있는데 비자 신청 가능한가요?` | EXC/cross_rule | RESP (범죄 경력 키워드 미매칭) |

### 2-2. 근본 원인

- **"난민", "망명"** 키워드가 `EXCEPTION_KEYWORDS`에 없음
- **"경범죄 기록"**, "기록이 있는데" 같은 간접 표현이 "범죄경력", "전과" 매칭에서 누락됨
- 국가 감지 없이 예외 유형만 있을 때 일부 경로가 general_chat으로 흘러감

### 2-3. 개선 전략

**A. `domain.py` 보강:**
```python
# 난민·망명
"난민": "cross_rule",
"망명": "cross_rule",
"보호 신청": "cross_rule",
"asylum": "cross_rule",
"refugee": "cross_rule",
# 범죄 기록 변형
"범죄 기록": "cross_rule",
"경범죄": "cross_rule",
"기록이 있": "cross_rule",   # 맥락 의존성 높아 주의 필요
```

> ⚠️ `"기록이 있"` 같이 광범위한 키워드는 FP 위험 → 테스트 후 결정

**B. 예외 LLM 안내 보강 (`response.py` exception prompt):**

난민/망명은 일반 비자와 근본적으로 다른 경로이므로, exception_handler 내부 프롬프트에
"비자 신청과 다른 보호 신청 절차임을 명확히 고지" 규칙 추가 필요.

### 2-4. 검증 케이스 (→ `scenarios_low_confidence.py` Group 2)
- 난민/망명 직접 표현
- 간접 범죄 기록 표현 ("기록이 있어요", "경범죄가 있는데")
- 국가 있음 + 난민
- 국가 없음 + 특수 신분

---

## 3. G3_FOLLOWUP 후반 대화 (T7+) — 컨텍스트 약화 및 오분류

### 3-1. 현상

v70 시나리오 G3는 10턴 체인을 사용. T7 이후 검증에서:

- **국가 컨텍스트 유실**: T7 이후 새 메시지에 국가 미언급 시 `country=None`으로 초기화
- **"거절"/"연장" 단어 → EXC 강제 라우팅**: T8에서 "이 비자가 거절될 가능성이 있나요?"
  → `detected_exception="rejection"` → exception_handler → **is_followup=False** → 전체 템플릿 출력 (사용자 입장 중복감)
- **is_followup 감지 하락**: 대화가 깊어질수록 LLM이 "이미 안내한 비자"라는 맥락을 잃음

### 3-2. 근본 원인

1. `intent.py` `is_deep_turn` 임계값이 5회이며, 이 이상에서는 컨텍스트 지시가 있지만 메시지 창이 마지막 6개 메시지만 포함 → T7+ 에서는 T1 안내 내용이 창 밖으로 벗어남
2. exception_handler 경로는 `is_followup`을 강제로 False 취급 → 중복 템플릿 출력

### 3-3. 개선 전략

**A. exception_handler 내 followup 압축 적용:**

T7+ deep turn에서 `detected_exception` 이 있더라도, 이미 동일 비자로 대화 중이라면
응답을 exception_handler 결과로 압축해서 전체 비자 추천 섹션을 반복하지 않도록 수정.

```python
# response.py 또는 exception_handler.py
if is_followup and is_exception:
    # exception 내용만 집중 출력, 전체 비자 추천 생략
    ...
```

**B. `intent.py` is_deep_turn 기준 세분화:**
- `turn_count >= 5`: 깊은 대화 (현재)
- `turn_count >= 8`: "매우 깊은 대화" — 국가/목적을 더 강하게 고정

**C. 메시지 창 확장 (선택):**

현재 `list(state["messages"][:-1][-6:])` → T7+에서는 `-10:` 로 확장 고려
(컨텍스트 길이 vs 비용 트레이드오프)

### 3-4. 검증 케이스 (→ `scenarios_low_confidence.py` Group 3)
- T8에서 "거절" 키워드 → EXC 라우팅 + 국가 유지 여부
- T9에서 일반 후속 질문 → is_followup=True 유지 여부
- T7에서 국가 교체 → 새 국가 올바르게 반영
- T8+ 압축 응답 여부 (is_followup=True 이면 short card)

---

## 4. 압축 워크플로우 엣지케이스 — is_followup 오감지

### 4-1. 현상

| 상황 | 예상 is_followup | 위험 |
|---|---|---|
| 첫 메시지가 "서류는요?" | False | LLM이 True로 판단 → 빈 압축 응답 |
| 1턴 후 바로 "비자 비용은요?" | True (적절) | — |
| 주제 전환 직후 "그 비자 기간은요?" | True (적절) | — |
| "아, 잘못 물었어요. 미국 비자는요?" | False (새 주제) | LLM이 True 유지 가능성 |
| 10턴 체인에서 갑자기 완전 다른 나라 질문 | False | LLM이 True 유지 가능성 |

### 4-2. 근본 원인

`is_followup` 감지는 LLM 판단에 전적으로 의존 (`intent.py` extraction_prompt의 JSON 필드).
엣지케이스에서 LLM이 "이전 대화와 연관된 질문처럼 보이면 True" 규칙을 과잉 적용할 수 있음.

### 4-3. 개선 전략

**A. `intent.py` is_followup 판단 기준 명시 강화:**

```python
# 현재 프롬프트에 추가할 지시
"is_followup": "true|false — 다음 조건을 모두 충족해야 true: "
              "(1) 이전 대화에서 이미 특정 비자가 안내됐고, "
              "(2) 지금 질문이 그 비자에 대한 세부 질문이며, "
              "(3) 사용자가 새 국가나 새 목적을 제시하지 않았을 때. "
              "첫 메시지이거나, 새 국가/목적이 나왔거나, "
              "이전 안내된 비자와 무관한 질문이면 반드시 false."
```

**B. Fallback 안전장치:**

- `has_prior_visa` 변수: `messages` 중 role=assistant 가 1개 이상이고 is_visa=True 인 메시지가 있어야만 True로 허용
- 첫 메시지(`len(messages) == 1`)이면 `is_followup = False` 강제

### 4-4. 검증 케이스 (→ `scenarios_low_confidence.py` Group 4)
- 첫 메시지만 있는 상태에서 "서류는요?" → False
- 정상 후속 2번째 메시지 → True
- 주제 전환 후 → False
- 전환 후 재후속 → True

---

## 5. 검증 우선순위 및 계획

| 우선순위 | 영역 | 예상 개선 효과 | 수정 난이도 |
|:---:|---|---|:---:|
| ★★★ | status_change 자연어 | 직접 키워드 추가 → 즉각 효과 | 낮음 |
| ★★★ | G2_EXC 난민/망명 | 키워드 2개 추가 | 낮음 |
| ★★☆ | is_followup 오감지 | 프롬프트 강화 | 중간 |
| ★★☆ | G3 T7+ 압축 | exception+followup 교차 처리 | 높음 |
| ★☆☆ | 메시지 창 확장 | 비용 증가 수반 | 중간 |

### 실행 계획

1. `domain.py` 키워드 추가 (status_change 동사형 + 난민/망명) — **즉시 적용 가능**
2. `intent.py` is_followup 판단 프롬프트 강화 — **즉시 적용 가능**
3. `tests/scenarios_low_confidence.py` 45개 시나리오 실행 → 결과 기록
4. 통과율 < 70% 영역에 대해 코드 수정 → 재검증
5. `/analytics` 페이지 Round 12 항목 추가

---

> 데이터셋: `tests/scenarios_low_confidence.py`  
> 실행기: `tests/run_low_confidence.py`  
> 결과: `tests/results_low_confidence.json`
