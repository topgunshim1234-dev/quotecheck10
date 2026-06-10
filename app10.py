import streamlit as st
import difflib
import re
import os

# ==========================================
# 1. 여러 권의 TXT 전문 통합 로드 엔진
# ==========================================
@st.cache_resource
def load_all_books_context(books_dict):
    """
    지정된 모든 책 파일들을 순회하며 페이지 번호를 제외한 
    텍스트 전문을 하나의 거대한 문자열로 통합하여 딕셔너리로 반환합니다.
    """
    all_books_db = {}
    
    for book_title, txt_path in books_dict.items():
        if not os.path.exists(txt_path):
            continue
        try:
            with open(txt_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            clean_lines = []
            for line in lines:
                stripped = line.strip()
                # 단독으로 있는 페이지 번호(숫자만 있는 줄) 제외
                if re.match(r'^\d+$', stripped):
                    continue
                if stripped:
                    clean_lines.append(stripped)

            # 책 한 권의 텍스트를 하나로 결합
            all_books_db[book_title] = " ".join(clean_lines)
        except Exception as e:
            st.error(f"[{book_title}] 파일 로드 중 오류 발생: {e}")
            
    return all_books_db

# ==========================================
# 2. 도서 목록 세팅 및 로드
# ==========================================
# 💡 여기에 다른 책들을 얼마든지 자유롭게 추가할 수 있습니다!
SUPPORTED_BOOKS = {
    "정의란 무엇인가 (마이클 샌델)": "2437)정의란 무엇인가 (마이클 샌델) .txt",
     "코스모스 (칼 세이건)": "코스모스 - 보급판 (칼 세이건) (z-librarysk, 1libsk, z-libs_260610_210711.txt",  
     "사피엔스 (유발 하라리)": "사피엔스 (유발 하라리 지음, 조현욱 옮김) (z-library.sk, 1lib.sk, z-lib.sk).txt"
}

BOOKS_DB = load_all_books_context(SUPPORTED_BOOKS)

# ==========================================
# 3. 전 도서 대상 실시간 검색 및 채점 엔진
# ==========================================
def analyze_quote_multi_books(selected_book, user_text):
    full_text = BOOKS_DB.get(selected_book, "")
    if not full_text:
        return 0, "데이터 오류", "해당 도서의 원문 데이터를 불러오지 못했습니다.", ""

    # 1. 부호와 공백을 모두 제거한 순수 자구 스트링 생성
    clean_origin_pool = re.sub(r'[^\w]', '', full_text)
    clean_user = re.sub(r'[^\w]', '', user_text)

    if not clean_user:
        return 0, "입력 오류", "검증할 문장을 입력해 주세요.", ""

    # 2. 초고속 문맥 매칭 및 구간 잘라오기
    search_query = user_text[:15] if len(user_text) > 15 else user_text
    start_pos = full_text.find(search_query)
    
    if start_pos != -1:
        matched_context = full_text[max(0, start_pos - 40): min(len(full_text), start_pos + len(user_text) + 150)]
    else:
        # 단어가 완벽히 일치하지 않으면 유사 매칭 블록 추적
        matcher = difflib.SequenceMatcher(None, clean_origin_pool, clean_user)
        match_blocks = matcher.get_matching_blocks()
        largest_match = max(match_blocks, key=lambda x: x.size)
        if largest_match.size > 0:
            matched_context = "책 안에서 유사한 도덕적/철학적 맥락을 탐색했습니다. 아래 일치도를 참고하세요."
        else:
            matched_context = "책 전체에서 유사한 문맥을 찾을 수 없습니다."

    # 3. 최종 점수 계산 및 보정
    clean_matched_segment = re.sub(r'[^\w]', '', matched_context)
    similarity_ratio = difflib.SequenceMatcher(None, clean_matched_segment, clean_user).ratio()
    
    if clean_user in clean_origin_pool:
        score = 100
    else:
        score = int(similarity_ratio * 100)
        # 부분 일치 확률 보정
        if 'largest_match' in locals() and largest_match.size > len(clean_user) * 0.5:
            score = max(score, int((largest_match.size / len(clean_user)) * 100))

    # 결과 분류
    if score >= 90:
        return score, "직접 인용 일치", "저자의 표현과 책 원문의 맥락이 완벽히 일치합니다. 왜곡 없는 정확한 인용입니다.", matched_context
    elif 50 <= score < 90:
        return score, "간접 인용 (말바꾸기 정황)", "의미는 통하지만 단어 순서나 조사, 표현이 원문과 다릅니다. 의도적인 요약인지 확인하세요.", matched_context
    else:
        return score, "출처 오류 및 문맥 왜곡 위험", "선택한 도서 전체를 통틀어 입력하신 문장과 유사한 맥락을 찾을 수 없습니다.", matched_context

# ==========================================
# 4. 세션 상태(Session State) 초기화
# ==========================================
if 'total_count' not in st.session_state: st.session_state['total_count'] = 0
if 'match_count' not in st.session_state: st.session_state['match_count'] = 0
if 'mismatch_count' not in st.session_state: st.session_state['mismatch_count'] = 0
if 'history_log' not in st.session_state: st.session_state['history_log'] = []

# ==========================================
# 5. 사용자 화면 구성 (UI)
# ==========================================
st.set_page_config(page_title="QuoteCheck", page_icon="📱")
st.title("📱 QuoteCheck")
st.caption("대학 글쓰기 인용 자구 검증 시스템 (다중 도서 지원 버전)")
st.markdown("---")

tab1, tab2 = st.tabs(["🔍 통합 인용 검증", "📋 인용 오답노트 (통계)"])

with tab1:
    st.subheader("인용구 실시간 검증")
    
    # 💡 나중에 SUPPORTED_BOOKS에 등록한 책들이 여기에 자동으로 다 뜨게 됩니다.
    selected_book = st.selectbox("📚 대상 도서 선택", list(SUPPORTED_BOOKS.keys()))
    
    # 해당 파일이 실제로 서버 폴더 내에 누락되었는지 체크
    target_file = SUPPORTED_BOOKS[selected_book]
    if not os.path.exists(target_file):
        st.error(f"⚠️ 현재 GitHub 폴더 내에서 '{target_file}' 파일을 찾을 수 없습니다. 파일 업로드 상태를 확인해 주세요.")
    else:
        user_quote = st.text_area("✍️ 자신이 작성한 에세이 속 인용구 입력", placeholder="검증하고 싶은 인용 문장을 자유롭게 입력하세요.", height=150)
        
        if st.button("🚀 선택한 책에서 원문 분석하기"):
            if not user_quote.strip():
                st.warning("문장을 입력해 주세요.")
            else:
                st.session_state['total_count'] += 1
                score, quote_type, feedback, context_snippet = analyze_quote_multi_books(selected_book, user_quote)
                
                # 결과별 신호등 UI
                if score >= 90:
                    status = "안전"
                    st.success(f"### 🟢 [{status}] 맥락 일치도: {score}%")
                    st.session_state['match_count'] += 1
                elif 50 <= score < 90:
                    status = "주의"
                    st.warning(f"### 🟡 [{status}] 맥락 일치도: {score}%")
                    st.session_state['mismatch_count'] += 1
                else:
                    status = "위험"
                    st.error(f"### 🔴 [{status}] 맥락 일치도: {score}%")
                    st.session_state['mismatch_count'] += 1
                
                # 자동으로 찾아낸 원문 영역 출력
                if context_snippet:
                    st.info(f"📖 **[{selected_book}] 시스템이 자동으로 찾아낸 관련 원문 구간:**\n\n\"... {context_snippet} ...\"")
                
                st.write(f"📊 **인용 판별 유형:** `{quote_type}`")
                st.markdown(f"**상세 피드백:**\n{feedback}")
                
                # 로그 저장
                st.session_state['history_log'].append({
                    "book": selected_book, "quote": user_quote, "score": score, "status": status
                })

with tab2:
    st.subheader("📋 개인 학습용 인용 통계 리포트")
    st.write("과제를 수행하며 인용구를 검사한 실제 누적 데이터 통계 대시보드입니다.")
    
    c1, c2, c3 = st.columns(3)
    c1.metric("총 검사 횟수", f"{st.session_state['total_count']}회")
    c2.metric("🟢 완벽 일치 횟수", f"{st.session_state['match_count']}회")
    c3.metric("⚠️ 교정 대상 횟수", f"{st.session_state['mismatch_count']}회")
    
    st.markdown("---")
    st.write("🕒 **최근 검사 이력 로그**")
    if not st.session_state['history_log']:
        st.caption("아직 검사한 내역이 없습니다.")
    else:
        for i, log in enumerate(reversed(st.session_state['history_log'])):
            st.markdown(f"**[{len(st.session_state['history_log'])-i}] [{log['book']}] 검사** | 점수: `{log['score']}%` ({log['status']})")
            st.caption(f"입력문장: \"{log['quote']}\"")
