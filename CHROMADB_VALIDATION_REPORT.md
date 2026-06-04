# ChromaDB 자가학습 검증 최종 보고서

**작성일**: 2026-06-04
**대상**: VisaGuide AI — `knowledge_writer` 자가학습 + RAG 재검색 사이클
**검증 모델**: claude-haiku-4-5 (실행) / claude-opus-4-8 (분석·보고)
**관련 파일**: `tests/scenarios_chroma_v50.py`, `tests/run_chroma_v50.py`, `tests/proof_chroma_cycle.py`

---

## 1. 검증 동기

> 사용자 요청: *"신규 국가나 최신 정보를 ChromaDB Vector 저장한다면서, 이를 증명해본 적은
> 없네. 이후 사용자 요청에서 찾고자 하는 정보가 ChromaDB에 있다면 검색할 필요 없이 참고하면
> 되니까 — 이것까지 고려해서 검증 50개를 진행해줘."*

핵심 질문 2가지:
1. **저장**: 신규 국가/최신 정보가 정말 ChromaDB에 학습 저장되는가?
2. **재활용**: 재요청 시 웹검색 없이 ChromaDB에서 직접 추출되는가?

---

## 2. 검증 구성 (2단계)

### Phase 1 — v50 배치 검증 (`results_chroma_v50.json`)
| Phase | 내용 | 개수 | 결과 |
|-------|------|------|------|
| A1 | status_change 재검증 | 8 | 6/8 (75.0%) |
| A2 | multi_turn 재검증 | 6 | 2/6 (33.3%) |
| A3 | conflicting 재검증 | 6 | 0/6 (0.0%) |
| B1 | 신규국가 첫 요청 → 웹검색+저장 | 15 | 0/15 (0.0%) |
| B2 | 동일국가 재요청 → RAG 재활용 | 15 | 14/15 (93.3%) |
| **계** | | **50** | **22/50 (44.0%)** |

### Phase 2 — 라이브 사이클 증명 (`results_chroma_cycle.json`)
DB **0건** 신규 국가 4개로 before/after 통제 실험.

---

## 3. 핵심 발견 — B1=0%는 "결함"이 아니라 "이미 학습됨"의 증거

### 3.1 ChromaDB 실측 현황
```
총 137 문서 = 사전적재 99 (origin=없음) + 자가학습 38 (origin=web_search)
```
**38개의 web_search 학습 문서가 이미 누적**돼 있었다 (이전 v180·라운드들의 검증 과정에서 축적).

### 3.2 B1 라우팅 실측
B1 테스트 15개국(PT·ES·AE·MY·TH·IT·NL·SE·DK·NO·IE·FI·ZA·BR·IN) **전부**가
`web=False, rag=True` → **웹검색 없이 곧장 RAG 직행**.

| 의미 | 해석 |
|------|------|
| 테스트 기대 | "신규국가" → web_search_tool 실행 |
| 실제 동작 | 이미 학습됨 → visa_rag_search 직행 |
| 결론 | **0%는 시스템 정상. 테스트 전제(미학습)가 틀림** |

즉, **자가학습 메커니즘이 이미 잘 작동해 와서** 해당 국가들이 더 이상 "신규"가 아니었던 것.
이를 통제하려면 DB 0건인 국가가 필요 → Phase 2 실행.

---

## 4. Phase 2 — 라이브 사이클 완전 증명 (4/4) ⭐

DB **0건**인 진짜 신규 국가 4개로 전체 사이클을 단계별 측정.

| 국가 | [0] BEFORE | [1] 1차 요청 경로 | [2] AFTER | [3] 재요청 경로 | 판정 |
|------|-----------|------------------|-----------|----------------|------|
| 🇮🇸 아이슬란드 | 0건 | intent→rag→**web→gate→writer✍**→resp | **1건 (+1)** | intent→**rag**→resp | ✅ |
| 🇱🇺 룩셈부르크 | 0건 | intent→rag→**web→gate→writer✍**→resp | **1건 (+1)** | intent→**rag**→resp | ✅ |
| 🇪🇪 에스토니아 | 0건 | intent→rag→**web→gate→writer✍**→resp | **1건 (+1)** | intent→**rag**→resp | ✅ |
| 🇺🇾 우루과이 | 0건 | intent→rag→**web→gate→writer✍**→resp | **1건 (+1)** | intent→**rag**→resp | ✅ |

```
완전 사이클 증명:          4/4 ✅
학습 저장 (DB 증가):       4/4 ✅
재요청 DB추출 (웹검색 없음): 4/4 ✅
```

**증명 완료**: 신규국가 첫 요청은 웹검색→`knowledge_writer`로 ChromaDB에 저장되고,
재요청 시 **웹검색 없이 `visa_rag_search`만으로** 응답한다. 사용자가 요청한
"DB에 있으면 검색 없이 참고" 동작이 라이브로 입증됨.

---

## 5. Phase A 재검증 결과 (v180 개선 영역)

### A1 status_change: 20% → **75%** ✅ (대폭 개선)
화살표·"전환"·"변경" 키워드 보강이 효과. 8개 중 6개가 `exception_handler` 정상 도달.

### A2 multi_turn: 42.9% → **33.3%** ⚠️ (여전히 미흡)
실패 4건 모두 수정신호("아니/사실은/미안해요") 후 **`response_formatter`로만 빠짐**:
```
"아니 사실은 유학만 하고 싶어요"     → response만 (기대: visa_rag_search)
"미안해요, 사실 일자리를 구하고 싶어요" → response만
"사실은 장기 거주가 목적이에요"       → response만
"그런데 3개월만 더 머물고 싶어요"     → visa_rag_search (기대: exception_handler)
```
**원인**: 수정신호 감지 시 이전 맥락(국가)을 비우면서 현재 메시지의 목적만 남아
국가가 없어 재질문(`response_formatter`)으로 빠짐. → **국가는 유지하고 목적만 교체**해야 함.

### A3 conflicting: 50% → **0%** 🔴 (회귀)
실패 6건 대부분 "X가 아니라 Y" → **`response_formatter`로만 빠짐**:
```
"관광이 아니라 취업으로 가고 싶어요"  → response만 (기대: exception_handler/visa_rag_search)
"여행이 아니라 이민을 생각하고 있어요" → response만
```
**원인**: 부정 패턴이 국가·목적 신호를 모두 무력화해 의도 추출이 비어버림.
→ 부정 뒤 **긍정 목적(Y)을 살려** 라우팅해야 함.

---

## 6. 결론 및 후속 과제

### ✅ 입증된 것
1. **ChromaDB 자가학습 사이클 완전 동작** (라이브 4/4)
   - 저장: 신규국가 → web_search → `knowledge_writer` → DB +1
   - 재활용: 재요청 → `visa_rag_search`만 (웹검색 생략)
2. **누적 효과 실측**: 검증을 거듭할수록 학습 문서가 쌓여(현재 38건) 웹검색 의존도 감소
3. **status_change 개선** (20% → 75%)

### 🔴 후속 과제 (Priority)
| # | 영역 | 현재 | 원인 | 해결 방향 |
|---|------|------|------|----------|
| P2 | multi_turn | 33.3% | 수정신호 시 국가까지 리셋 | 국가 유지 + 목적만 교체 |
| P3 | conflicting | 0% | 부정이 모든 신호 무력화 | "X 아니라 Y"의 Y 살리기 |

이 두 패턴은 공통적으로 **`intent.py`의 `_NEGATION_RE` 처리 로직**에서 비롯됨.
부정 신호 감지 후 "이전 맥락 전체 폐기"가 과도 → **국가는 보존하고 목적/유형만 갱신**하도록
수정하면 두 영역 동시 개선 가능.

---

## 7. 산출물

| 파일 | 내용 |
|------|------|
| `tests/scenarios_chroma_v50.py` | 50개 검증 시나리오 (Phase A/B) |
| `tests/run_chroma_v50.py` | v50 배치 실행기 (B1→대기→B2 순서 보장) |
| `tests/proof_chroma_cycle.py` | 라이브 사이클 증명기 (before/after) |
| `tests/results_chroma_v50.{json,log}` | v50 배치 결과 |
| `tests/results_chroma_cycle.json` | 라이브 사이클 결과 (4/4) |
| `VERSION.md` | v0.10.0 검증 결과 반영 |
| `CHROMADB_VALIDATION_REPORT.md` | 본 보고서 |

---

**최종 판정**: ChromaDB 자가학습·재검색 메커니즘 **검증 완료 (라이브 4/4 증명)**.
Phase A multi_turn·conflicting은 `intent.py` 부정신호 처리 개선으로 후속 대응 예정.
