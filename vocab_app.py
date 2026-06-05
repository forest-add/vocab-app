import streamlit as st
import pandas as pd
import random
from datetime import datetime, timedelta
import os

# ========== 页面配置 ==========
st.set_page_config(page_title="大学葡萄牙语背单词助手", page_icon="📚", layout="wide")

st.title("📚 大学葡萄牙语智能背单词助手")
st.markdown("*基于《大学葡萄牙语1、2》教材词汇库 | 葡语→中文选择题模式 | SM-2遗忘曲线算法*")

# ========== 从CSV文件读取单词 ==========
@st.cache_data
def load_words():
    csv_path = "palavras.csv"
    if not os.path.exists(csv_path):
        st.error(f"❌ 找不到单词文件：{csv_path}")
        st.info("请确保 `palavras.csv` 文件与本程序在同一文件夹下")
        return pd.DataFrame()
    
    try:
        df = pd.read_csv(csv_path, encoding='utf-8')
        # 检查必需的列
        required_columns = ["葡语", "中文", "词性", "单元", "难度"]
        for col in required_columns:
            if col not in df.columns:
                st.error(f"❌ CSV文件缺少列：{col}")
                return pd.DataFrame()
        df["难度"] = pd.to_numeric(df["难度"], errors='coerce').fillna(1).astype(int)
        return df
    except Exception as e:
        st.error(f"❌ 读取CSV文件失败：{e}")
        return pd.DataFrame()

# ========== 初始化学习记录 ==========
def init_learning_records(words_df):
    records = {}
    for _, word in words_df.iterrows():
        records[word["葡语"]] = {
            "正确次数": 0,
            "错误次数": 0,
            "连续正确": 0,
            "下次复习": datetime.now().strftime("%Y-%m-%d")
        }
    return records

# ========== SM-2算法 ==========
def calculate_next_review(连续正确):
    intervals = {0: 1, 1: 3, 2: 7, 3: 14, 4: 30}
    return intervals.get(连续正确, 60)

# ========== 生成中文选项 ==========
def generate_chinese_options(correct_word, words_df, num_options=4):
    correct_row = words_df[words_df["葡语"] == correct_word]
    if correct_row.empty:
        return ["错误"], "错误"
    correct_chinese = correct_row["中文"].iloc[0]
    
    other_words = words_df[words_df["葡语"] != correct_word]
    other_chinese = other_words["中文"].tolist()
    other_chinese = list(set(other_chinese))
    
    if len(other_chinese) >= num_options - 1:
        distractors = random.sample(other_chinese, num_options - 1)
    else:
        distractors = other_chinese.copy()
        while len(distractors) < num_options - 1:
            distractors.append("待补充")
    
    options = distractors + [correct_chinese]
    random.shuffle(options)
    return options, correct_chinese

# ========== 获取推荐单词队列 ==========
def get_recommendation_queue(words_df, records, current_unit_prefix=None, num_words=10):
    今日 = datetime.now().date()
    
    if current_unit_prefix:
        available_words = words_df[words_df["单元"].str.startswith(current_unit_prefix)]
    else:
        available_words = words_df
    
    if available_words.empty:
        return []
    
    need_review = []
    for _, word in available_words.iterrows():
        palavra = word["葡语"]
        info = records.get(palavra)
        if info is None:
            continue
        next_date = datetime.strptime(info["下次复习"], "%Y-%m-%d").date()
        if next_date <= 今日:
            priority = info["错误次数"] * 0.7 + (5 - min(info["连续正确"], 5)) * 0.3
            need_review.append((palavra, priority))
    
    need_review.sort(key=lambda x: x[1], reverse=True)
    review_words = [w[0] for w in need_review]
    
    learned_words = [p for p, info in records.items() if info["正确次数"] > 0]
    new_words = available_words[~available_words["葡语"].isin(learned_words)]
    new_words = new_words.sort_values(["单元", "难度"])["葡语"].tolist()
    
    queue = review_words + new_words
    return queue[:num_words]

# ========== 更新学习记录 ==========
def update_record(records, palavra, is_correct):
    info = records[palavra]
    if is_correct:
        info["正确次数"] += 1
        info["连续正确"] += 1
        interval = calculate_next_review(info["连续正确"])
        info["下次复习"] = (datetime.now() + timedelta(days=interval)).strftime("%Y-%m-%d")
    else:
        info["错误次数"] += 1
        info["连续正确"] = 0
        info["下次复习"] = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    return records

def next_question():
    st.session_state.current_index += 1
    st.session_state.answer_feedback = None
    st.session_state.current_options = []
    st.session_state.correct_answer = None

# ========== Session State 初始化 ==========
if 'words_df' not in st.session_state:
    st.session_state.words_df = load_words()

if st.session_state.words_df.empty:
    st.stop()

if 'records' not in st.session_state:
    st.session_state.records = init_learning_records(st.session_state.words_df)

if 'current_unit_prefix' not in st.session_state:
    st.session_state.current_unit_prefix = "1"

if 'quiz_queue' not in st.session_state:
    st.session_state.quiz_queue = []

if 'current_index' not in st.session_state:
    st.session_state.current_index = 0

if 'answer_feedback' not in st.session_state:
    st.session_state.answer_feedback = None

if 'current_options' not in st.session_state:
    st.session_state.current_options = []

if 'correct_answer' not in st.session_state:
    st.session_state.correct_answer = None

def refresh_queue():
    st.session_state.quiz_queue = get_recommendation_queue(
        st.session_state.words_df,
        st.session_state.records,
        st.session_state.current_unit_prefix,
        num_words=10
    )
    st.session_state.current_index = 0
    st.session_state.answer_feedback = None
    st.session_state.current_options = []
    st.session_state.correct_answer = None

if not st.session_state.quiz_queue:
    refresh_queue()

# ========== 侧边栏 ==========
with st.sidebar:
    st.header("📖 教材选择")
    
    unit_option = st.radio(
        "选择学习范围",
        ["第1册", "第2册", "全部"],
        index=0
    )
    
    if unit_option == "第1册":
        new_prefix = "1"
    elif unit_option == "第2册":
        new_prefix = "2"
    else:
        new_prefix = None
    
    if new_prefix != st.session_state.current_unit_prefix:
        st.session_state.current_unit_prefix = new_prefix
        refresh_queue()
        st.rerun()
    
    st.divider()
    st.header("📊 学习统计")
    
    if st.session_state.current_unit_prefix:
        available_words = st.session_state.words_df[
            st.session_state.words_df["单元"].str.startswith(st.session_state.current_unit_prefix)
        ]
    else:
        available_words = st.session_state.words_df
    
    if not available_words.empty:
        reviewed_count = sum(1 for p in available_words["葡语"] 
                            if st.session_state.records.get(p, {}).get("正确次数", 0) > 0)
        total_correct = sum(st.session_state.records.get(p, {}).get("正确次数", 0) for p in available_words["葡语"])
        total_errors = sum(st.session_state.records.get(p, {}).get("错误次数", 0) for p in available_words["葡语"])
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("已学单词", f"{reviewed_count}/{len(available_words)}")
            st.metric("总正确", total_correct)
        with col2:
            st.metric("剩余单词", len(available_words) - reviewed_count)
            st.metric("总错误", total_errors)
        
        if total_correct + total_errors > 0:
            accuracy = total_correct / (total_correct + total_errors)
            st.progress(accuracy)
            st.caption(f"正确率：{accuracy:.1%}")
    
    st.divider()
    
    if st.button("🔄 重置进度", use_container_width=True):
        st.session_state.records = init_learning_records(st.session_state.words_df)
        refresh_queue()
        st.rerun()
    
    st.caption("📚 词库：palavras.csv")
    st.caption("⚡ 算法：SM-2 | 答错明天必复习")

# ========== 主界面 ==========
st.subheader("📖 选择题模式")

if st.session_state.current_index < len(st.session_state.quiz_queue):
    current_word = st.session_state.quiz_queue[st.session_state.current_index]
    word_info = st.session_state.words_df[st.session_state.words_df["葡语"] == current_word]
    
    if word_info.empty:
        st.session_state.current_index += 1
        st.rerun()
    
    word_info = word_info.iloc[0]
    
    st.progress((st.session_state.current_index) / len(st.session_state.quiz_queue))
    st.caption(f"第 {st.session_state.current_index + 1} / {len(st.session_state.quiz_queue)} 题")
    
    unit_label = word_info["单元"]
    if unit_label.startswith("2"):
        unit_display = f"第2册 {unit_label.replace('2-', 'U')}"
    else:
        unit_display = f"第1册 {unit_label.replace('1-', 'U')}"
    
    with st.container():
        st.markdown(f"""
        <div style="background-color: #f0f2f6; padding: 2rem; border-radius: 10px; text-align: center;">
            <h2 style="color: #1f1f1f;">{current_word}</h2>
            <p style="color: #666;">{word_info['词性']} | {unit_display} | 难度：{'⭐' * word_info['难度']}</p>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("### 请选择正确的中文释义：")
        
        if not st.session_state.current_options:
            st.session_state.current_options, st.session_state.correct_answer = generate_chinese_options(
                current_word, st.session_state.words_df
            )
        
        cols = st.columns(2)
        for i, option in enumerate(st.session_state.current_options):
            col = cols[i % 2]
            is_disabled = st.session_state.answer_feedback is not None
            
            if col.button(f"{chr(65+i)}. {option}", key=f"opt_{i}_{current_word}", 
                          use_container_width=True, disabled=is_disabled):
                is_correct = (option == st.session_state.correct_answer)
                st.session_state.records = update_record(
                    st.session_state.records, current_word, is_correct
                )
                if is_correct:
                    st.session_state.answer_feedback = f"✅ 正确！「{current_word}」的意思是 {st.session_state.correct_answer}"
                else:
                    st.session_state.answer_feedback = f"❌ 错误。正确答案是 {st.session_state.correct_answer}"
                st.rerun()
        
        if st.session_state.answer_feedback:
            if "✅" in st.session_state.answer_feedback:
                st.success(st.session_state.answer_feedback)
            else:
                st.error(st.session_state.answer_feedback)
            
            if st.button("➡️ 下一题", use_container_width=True):
                next_question()
                st.rerun()
else:
    st.success("🎉 恭喜！今天的所有单词都学完了！")
    if st.button("🔄 开始新一轮学习", use_container_width=True):
        refresh_queue()
        st.rerun()