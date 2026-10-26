"""디자인 시스템 · 혼디 제주.

- 색: 흰 배경 + 회색 단계 + 제주 감귤 주황 포인트. 상태색(좋음/주의/위험)은 상태 표시에만 씁니다.
  주황 글자는 진한 단계(--brand-text, 대비 5.6:1)만, 흰 글자 버튼은 --brand-strong 위 18px 굵게(대형 글자 기준 충족).
- 글자: Pretendard, 본문 17px, 모든 본문 대비 4.5:1 이상.
- 터치: 버튼·입력 최소 높이 52px, 키보드 포커스 링 3px.
- 접근성 옵션: 큰 글씨(115%), 고대비(진한 글자·테두리).
"""
import streamlit as st

from ui.components import tidy

_BASE = """
<style>
@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css');

:root {
  --brand: #F2650A; --brand-strong: #E05200; --brand-press: #C44700; --brand-text: #B84300; --brand-weak: #FFF1E6; --brand-weak-2: #FFE0C7;
  --info: #2F6FED; --info-weak: #EAF1FE;
  --ink: #191F28; --ink-2: #333D4B; --ink-3: #4E5968; --ink-4: #6B7684;
  --line: #E5E8EB; --line-2: #D1D6DB; --fill: #F2F4F6; --fill-2: #F9FAFB; --surface: #FFFFFF;
  --good: #00804A; --good-weak: #E5F6EE; --warn: #9A5B00; --warn-weak: #FFF5D6;
  --bad: #D22030; --bad-weak: #FFEBEC;
  --radius: 20px; --radius-s: 14px;
  --shadow: 0 1px 2px rgba(0,0,0,.04), 0 4px 16px rgba(0,0,0,.04);
}

html, body, [class*="css"], .stApp, button, input, textarea, select {
  font-family: 'Pretendard Variable', Pretendard, -apple-system, BlinkMacSystemFont, 'Apple SD Gothic Neo', sans-serif !important;
  -webkit-font-smoothing: antialiased;
}
.stApp { background: var(--surface) !important; color: var(--ink); }
[data-testid="stHeader"], [data-testid="stToolbar"], [data-testid="stDecoration"], footer, #MainMenu,
[data-testid="stAppDeployButton"], [data-testid="stStatusWidget"] { display: none !important; }
[data-testid="stMainBlockContainer"], .block-container { max-width: 1080px !important; padding: 0 24px 96px !important; }
@media (max-width: 640px) { [data-testid="stMainBlockContainer"], .block-container { padding: 0 16px 80px !important; } }

p, li, label, span, div { letter-spacing: -0.01em; }
.stMarkdown p, .stMarkdown li { font-size: 17px; line-height: 1.65; color: var(--ink-2); }
h1, h2, h3, h4 { color: var(--ink) !important; letter-spacing: -0.03em !important; font-weight: 700 !important; }
[data-testid="stCaptionContainer"], .stCaption, small { color: var(--ink-4) !important; font-size: 15px !important; }
a { color: var(--brand-text); }

/* ---------- 상단 바 ---------- */
.st-key-topbar { position: sticky; top: 0; z-index: 50; background: rgba(255,255,255,.92); backdrop-filter: saturate(180%) blur(16px);
  margin: 0 -24px 8px; padding: 14px 24px 0; border-bottom: 1px solid var(--line); }
@media (max-width: 640px) { .st-key-topbar { margin: 0 -16px 8px; padding: 10px 16px 0; } }
.brand { display: flex; align-items: center; gap: 10px; height: 48px; }
.brand-mark { width: 34px; height: 34px; border-radius: 11px; background: linear-gradient(140deg, #FF8A2B, #E85500); display: grid; place-items: center; box-shadow: 0 4px 10px rgba(242,101,10,.3); }
.brand-name { font-size: 20px; font-weight: 800; color: var(--ink); letter-spacing: -0.04em; }
.brand-sub { font-size: 14px; color: var(--ink-4); font-weight: 500; }
@media (max-width: 640px) { .brand-sub { display: none; } }

/* 내비게이션: 라디오를 탭 막대처럼 */
.st-key-topbar [data-testid="stRadio"] > label { display: none; }
.st-key-topbar [role="radiogroup"] { flex-wrap: nowrap !important; overflow-x: auto; gap: 4px !important; scrollbar-width: none; }
.st-key-topbar [role="radiogroup"]::-webkit-scrollbar { display: none; }
.st-key-topbar [role="radiogroup"] label { margin: 0 !important; padding: 12px 14px 14px !important; min-height: 48px; border-bottom: 3px solid transparent !important;
  cursor: pointer; white-space: nowrap; border-radius: 0; }
.st-key-topbar [role="radiogroup"] label > div > div:first-child:not([data-testid]) { display: none !important; }
.st-key-topbar [role="radiogroup"] label p { font-size: 17px !important; font-weight: 600 !important; color: var(--ink-4) !important; }
.st-key-topbar [role="radiogroup"] label:hover p { color: var(--ink-2) !important; }
.st-key-topbar [role="radiogroup"] label[data-selected="true"] { border-bottom: 3px solid var(--brand) !important; }
.st-key-topbar [role="radiogroup"] label[data-selected="true"] p { color: var(--ink) !important; font-weight: 700 !important; }
.st-key-topbar [role="radiogroup"] label { outline: none !important; box-shadow: none !important; border-top: 0 !important; border-left: 0 !important; border-right: 0 !important; }
.st-key-topbar [role="radiogroup"] label[data-focus-visible="true"] { outline: 3px solid var(--brand); outline-offset: -3px; border-radius: 8px; }

/* ---------- 버튼 ---------- */
.stButton > button, .stFormSubmitButton > button, .stLinkButton > a, .stDownloadButton > button {
  min-height: 56px !important; border-radius: var(--radius-s) !important; font-size: 17px !important; font-weight: 600 !important;
  padding: 0 20px !important; transition: background .15s ease, transform .1s ease !important; box-shadow: none !important; }
.stButton button p, .stFormSubmitButton button p, .stLinkButton a p, [data-testid="stPopover"] button p { font-size: 17px !important; font-weight: 600 !important; }
[data-testid="stPopover"] button { min-height: 48px !important; border-radius: 12px !important; border: 1px solid var(--line) !important; }
.stButton > button:active, .stFormSubmitButton > button:active, .stLinkButton > a:active { transform: scale(.98); }
[data-testid^="stBaseButton-primary"], [data-testid="stBaseLinkButton-primary"] { background: var(--brand-strong) !important; border: none !important; color: #fff !important; box-shadow: 0 6px 16px rgba(224,82,0,.22) !important; }
[data-testid^="stBaseButton-primary"] p, [data-testid="stBaseLinkButton-primary"] p { font-size: 18px !important; font-weight: 700 !important; }
[data-testid^="stBaseButton-primary"]:hover, [data-testid="stBaseLinkButton-primary"]:hover { background: var(--brand-press) !important; }
[data-testid^="stBaseButton-primary"] p, [data-testid="stBaseLinkButton-primary"] p { color: #fff !important; }
[data-testid^="stBaseButton-secondary"], [data-testid="stBaseLinkButton-secondary"] { background: var(--fill) !important; border: none !important; color: var(--ink-2) !important; }
[data-testid^="stBaseButton-secondary"]:hover, [data-testid="stBaseLinkButton-secondary"]:hover { background: #E5E8EB !important; }
[data-testid^="stBaseButton-secondary"] p { color: var(--ink-2) !important; }
[data-testid^="stBaseButton-tertiary"] { min-height: 48px !important; color: var(--brand-text) !important; }
[data-testid^="stBaseButton-tertiary"] p { color: var(--brand-text) !important; font-weight: 600 !important; }
button:disabled { opacity: .45 !important; }
button:focus-visible, a:focus-visible, input:focus-visible, textarea:focus-visible, [role="slider"]:focus-visible, [role="button"]:focus-visible {
  outline: 3px solid var(--brand) !important; outline-offset: 2px !important; }

/* 위험 버튼 (SOS) */
[class*="st-key-sos"] button, [class*="st-key-sos"] a { background: var(--bad) !important; color: #fff !important; box-shadow: 0 6px 16px rgba(210,32,48,.25) !important; }
.st-key-sos button:hover { background: #B01A28 !important; }

/* ---------- 입력 ---------- */
[data-testid="stWidgetLabel"] p, .stSlider label p, .stRadio > label p { font-size: 16px !important; font-weight: 600 !important; color: var(--ink-2) !important; }
[data-baseweb="input"], [data-baseweb="textarea"], [data-baseweb="select"] > div {
  background: var(--fill) !important; border: 2px solid transparent !important; border-radius: var(--radius-s) !important; min-height: 56px !important; }
[data-baseweb="input"] input { min-height: 52px !important; padding: 0 16px !important; }
[data-baseweb="select"] > div { padding-left: 8px !important; align-items: center !important; }
[data-baseweb="input"]:focus-within, [data-baseweb="textarea"]:focus-within, [data-baseweb="select"] > div:focus-within { border-color: var(--brand) !important; background: #fff !important; }
[data-baseweb="input"] input, [data-baseweb="textarea"] textarea { font-size: 17px !important; color: var(--ink) !important; background: transparent !important; }
[data-baseweb="input"] input::placeholder, textarea::placeholder { color: var(--ink-4) !important; }
[data-baseweb="select"] div { font-size: 17px !important; color: var(--ink); }

/* 칩(pills / segmented) */
[data-testid="stButtonGroup"] { gap: 8px !important; flex-wrap: wrap; }
[data-testid="stButtonGroup"] button[data-variant] {
  min-height: 48px !important; padding: 0 18px !important; border-radius: 999px !important; border: 1.5px solid var(--line-2) !important;
  background: #fff !important; font-size: 16px !important; }
[data-testid="stButtonGroup"] button[data-variant] p { font-size: 16px !important; font-weight: 600 !important; color: var(--ink-3) !important; }
[data-testid="stButtonGroup"] button[data-variant][data-selected="true"] { background: var(--ink) !important; border-color: var(--ink) !important; }
[data-testid="stButtonGroup"] button[data-variant][data-selected="true"] p { color: #fff !important; }
[data-testid="stButtonGroup"] button[data-variant="segmented_control"] { border-radius: 12px !important; }

/* 토글·체크박스 */
[data-testid="stCheckbox"] label { min-height: 44px; align-items: center; }
[data-testid="stCheckbox"] label p { font-size: 17px !important; color: var(--ink-2) !important; }

/* 슬라이더 */
[data-testid="stSlider"] [role="slider"] { width: 26px !important; height: 26px !important; background: #fff !important; border: 3px solid var(--brand) !important; box-shadow: var(--shadow) !important; }
[data-testid="stSliderThumbValue"], [data-testid="stSliderTickBarMin"], [data-testid="stSliderTickBarMax"] { font-size: 15px !important; color: var(--ink-3) !important; font-family: inherit !important; }

/* 컨테이너 카드 */
[data-testid="stVerticalBlockBorderWrapper"], div[data-testid="stVerticalBlock"][class*="st-key-card"] { border-radius: var(--radius) !important; }
.st-key-panel, [class*="st-key-panel_"] { background: var(--fill-2); border: 1px solid var(--line); border-radius: var(--radius); padding: 24px; }
@media (max-width: 640px) { .st-key-panel, [class*="st-key-panel_"] { padding: 18px; } }

/* 탭 */
.stTabs [data-baseweb="tab-list"] { gap: 4px; border-bottom: 1px solid var(--line); }
.stTabs [data-baseweb="tab"] { min-height: 52px; padding: 0 14px; }
.stTabs [data-baseweb="tab"] p { font-size: 17px !important; font-weight: 600 !important; color: var(--ink-4) !important; }
.stTabs [aria-selected="true"] p { color: var(--ink) !important; }
.stTabs [data-baseweb="tab-highlight"], .stTabs .react-aria-SelectionIndicator { background: var(--ink) !important; height: 3px !important; }
[data-testid="stTab"] { min-height: 52px; padding: 0 14px !important; }
[data-testid="stTab"] p { font-size: 17px !important; font-weight: 600 !important; color: var(--ink-4) !important; }
[data-testid="stTab"][data-selected="true"] p { color: var(--ink) !important; }

/* expander */
[data-testid="stExpander"] details { border: 1px solid var(--line) !important; border-radius: var(--radius-s) !important; }
[data-testid="stExpander"] summary { min-height: 56px; }
[data-testid="stExpander"] summary p { font-size: 17px !important; font-weight: 600 !important; color: var(--ink) !important; }

/* 다이얼로그 */
div[role="dialog"] { border-radius: 24px !important; }
div[role="dialog"] h2 { font-size: 22px !important; }

/* 알림 */
[data-testid="stAlert"] { border-radius: var(--radius-s) !important; }
[data-testid="stAlert"] p { font-size: 16px !important; }

/* 지도 iframe */
iframe { border-radius: var(--radius); }
.stElementContainer:has(iframe[title="streamlit_components.v1.components.html"]),
.element-container:has(iframe) { border-radius: var(--radius); overflow: hidden; }

/* ---------- 콘텐츠 블록 ---------- */
.hero { padding: 56px 0 32px; }
.hero .eyebrow { display: inline-flex; gap: 6px; align-items: center; font-size: 15px; font-weight: 600; color: var(--brand-text); background: var(--brand-weak); padding: 6px 12px; border-radius: 999px; }
.hero h1 { font-size: clamp(34px, 5.6vw, 54px) !important; line-height: 1.22 !important; font-weight: 800 !important; margin: 20px 0 16px !important; padding: 0 !important; }
.hero p.lead { font-size: clamp(17px, 2.2vw, 20px); color: var(--ink-3); line-height: 1.6; margin: 0; }
.page-head { padding: 36px 0 20px; }
.page-head h2 { font-size: clamp(26px, 4vw, 34px) !important; font-weight: 800 !important; margin: 0 0 8px !important; padding: 0 !important; line-height: 1.3 !important; }
.page-head p { font-size: 17px; color: var(--ink-3); margin: 0; line-height: 1.6; }
.section-title { font-size: 21px; font-weight: 700; color: var(--ink); margin: 32px 0 12px; letter-spacing: -0.03em; display: flex; align-items: baseline; gap: 8px; }
.section-title small { font-size: 15px; color: var(--ink-4); font-weight: 500; }

.card { background: var(--surface); border: 1px solid var(--line); border-radius: var(--radius); padding: 22px; height: 100%; }
.card.soft { background: var(--fill-2); }
.card.flat { border: none; background: var(--fill); }
.card h4 { font-size: 19px !important; margin: 0 0 6px !important; padding: 0 !important; font-weight: 700 !important; line-height: 1.4 !important; }
.card p { margin: 0; font-size: 16px; color: var(--ink-3); line-height: 1.6; }
.card .meta { font-size: 15px; color: var(--ink-4); }
.feature { display: flex; flex-direction: column; gap: 14px; min-height: 196px; }
.feature .ico { width: 48px; height: 48px; border-radius: 14px; background: var(--brand-weak); color: var(--brand); display: grid; place-items: center; }

.chips { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 10px; }
.chip { display: inline-flex; align-items: center; gap: 4px; padding: 5px 10px; border-radius: 8px; background: var(--fill); color: var(--ink-3); font-size: 14px; font-weight: 600; }
.chip.brand { background: var(--brand-weak); color: var(--brand-text); }
.chip.good { background: var(--good-weak); color: var(--good); }
.chip.warn { background: var(--warn-weak); color: var(--warn); }
.chip.bad { background: var(--bad-weak); color: var(--bad); }
.grade { display: inline-grid; place-items: center; width: 34px; height: 34px; border-radius: 10px; font-weight: 800; font-size: 16px; }
.grade.A { background: var(--good-weak); color: var(--good); } .grade.B { background: var(--info-weak); color: var(--info); }
.grade.C { background: var(--warn-weak); color: var(--warn); } .grade.D { background: var(--bad-weak); color: var(--bad); }

.stat { padding: 20px; border-radius: var(--radius); background: var(--fill); height: 100%; }
.stat .k { font-size: 15px; color: var(--ink-3); font-weight: 600; }
.stat .v { font-size: 30px; font-weight: 800; color: var(--ink); letter-spacing: -0.03em; margin-top: 4px; line-height: 1.2; }
.stat .v small { font-size: 16px; color: var(--ink-4); font-weight: 600; margin-left: 2px; }
.stat .s { font-size: 14px; margin-top: 6px; font-weight: 600; display: flex; align-items: center; gap: 4px; }

.row { display: flex; align-items: center; gap: 14px; padding: 16px 0; border-bottom: 1px solid var(--line); }
.row:last-child { border-bottom: none; }
.row .grow { flex: 1; min-width: 0; }
.row .t { font-size: 17px; font-weight: 600; color: var(--ink); }
.row .d { font-size: 15px; color: var(--ink-4); margin-top: 2px; }

/* 타임라인 */
.tl { position: relative; padding-left: 52px; }
.tl-item { position: relative; padding-bottom: 20px; }
.tl-item:before { content: ""; position: absolute; left: -33px; top: 40px; bottom: -4px; width: 2px; background: var(--line); }
.tl-item:last-child:before { display: none; }
.tl-dot { position: absolute; left: -52px; top: 0; width: 40px; height: 40px; border-radius: 50%; background: var(--brand); color: #fff;
  display: grid; place-items: center; font-weight: 700; font-size: 16px; }
.tl-dot.meal, .tl-dot.cafe { background: var(--ink); color: #fff; }
.tl-move { font-size: 14px; color: var(--ink-4); margin: -6px 0 12px; display: flex; gap: 6px; align-items: center; font-weight: 500; }
.tl-card { border: 1px solid var(--line); border-radius: var(--radius); padding: 18px 20px; background: #fff; }
.tl-time { font-size: 15px; font-weight: 700; color: var(--brand-text); }
.tl-card { transition: border-color .15s ease, box-shadow .15s ease; }
.tl-card:hover { border-color: var(--brand-weak-2); box-shadow: var(--shadow); }
.tl-card h4 { font-size: 19px !important; margin: 4px 0 2px !important; padding: 0 !important; }
.tl-note { display: flex; gap: 8px; align-items: flex-start; margin: 10px 0 2px; padding: 12px 14px; background: var(--brand-weak); border-radius: 12px; font-size: 16px; line-height: 1.55; color: var(--ink-2); }
.tl-note svg { flex: none; margin-top: 3px; color: var(--brand-text); }
.ai-theme { min-height: 268px; border-color: var(--brand-weak-2); background: linear-gradient(180deg, var(--brand-weak) 0%, #fff 55%); }
.ai-theme .eyebrow { background: #fff; color: var(--brand-text); border: 1px solid var(--brand-weak-2); }
.ai-theme h4 { margin: 14px 0 6px !important; padding: 0 !important; font-size: 20px !important; }
.ai-theme p { color: var(--ink-3); font-size: 16px; line-height: 1.6; margin: 0 0 12px; }
.st-key-panel_ai { background: linear-gradient(135deg, var(--brand-weak) 0%, #fff 70%) !important; border-color: var(--brand-weak-2) !important; }
.tl-tips { margin: 12px 0 0; padding: 12px 14px; background: var(--fill-2); border-radius: 12px; list-style: none; }
.tl-tips li { font-size: 15px !important; color: var(--ink-3) !important; line-height: 1.55 !important; padding: 2px 0; }
.tl-tips li b { color: var(--ink-2); font-weight: 600; }

/* 상태 배너 */
.banner { display: flex; gap: 14px; align-items: flex-start; padding: 18px 20px; border-radius: var(--radius); }
.banner .ico { flex: none; width: 40px; height: 40px; border-radius: 12px; display: grid; place-items: center; background: rgba(255,255,255,.7); }
.banner h4 { font-size: 18px !important; margin: 0 0 4px !important; padding: 0 !important; }
.banner p { margin: 0; font-size: 16px; line-height: 1.55; color: var(--ink-2); }
.banner.good { background: var(--good-weak); } .banner.good .ico { color: var(--good); }
.banner.caution { background: var(--warn-weak); } .banner.caution .ico { color: var(--warn); }
.banner.rest { background: var(--warn-weak); } .banner.rest .ico { color: var(--warn); }
.banner.danger { background: var(--bad-weak); } .banner.danger .ico { color: var(--bad); }
.banner.info { background: var(--brand-weak); } .banner.info .ico { color: var(--brand-text); }
.banner.neutral { background: var(--fill); } .banner.neutral .ico { color: var(--ink-3); }

/* 점수 게이지 */
.gauge { display: flex; align-items: center; gap: 22px; }
.gauge .ring { --p: 50; --c: var(--brand); width: 132px; height: 132px; border-radius: 50%; flex: none;
  background: conic-gradient(var(--c) calc(var(--p) * 1%), var(--fill) 0); display: grid; place-items: center; }
.gauge .ring > div { width: 104px; height: 104px; border-radius: 50%; background: #fff; display: grid; place-items: center; text-align: center; }
.gauge .num { font-size: 36px; font-weight: 800; color: var(--ink); line-height: 1; }
.gauge .unit { font-size: 13px; color: var(--ink-4); font-weight: 600; }
.bar { height: 8px; border-radius: 99px; background: var(--fill); overflow: hidden; }
.bar > i { display: block; height: 100%; border-radius: 99px; background: var(--brand); }

.factor { display: grid; grid-template-columns: 1fr auto; gap: 2px 12px; padding: 14px 0; border-bottom: 1px solid var(--line); }
.factor:last-child { border-bottom: none; }
.factor .n { font-size: 16px; font-weight: 600; color: var(--ink-2); }
.factor .val { font-size: 16px; font-weight: 700; color: var(--ink); text-align: right; }
.factor .note { grid-column: 1 / -1; font-size: 14px; color: var(--ink-4); display: flex; align-items: center; gap: 6px; }

.avatar { width: 56px; height: 56px; border-radius: 50%; background: var(--fill); color: var(--ink-3); display: grid; place-items: center; font-weight: 700; font-size: 20px; flex: none; }
.empty { text-align: center; padding: 48px 20px; border-radius: var(--radius); background: var(--fill-2); color: var(--ink-4); }
.empty h4 { color: var(--ink-2) !important; font-size: 18px !important; margin: 12px 0 4px !important; }
.demo-tag { display: inline-block; font-size: 13px; font-weight: 700; color: var(--ink-3); background: var(--fill); border-radius: 6px; padding: 3px 8px; margin-left: 6px; vertical-align: middle; }
.stepper { display: flex; gap: 6px; margin: 8px 0 4px; }
.stepper > div { flex: 1; text-align: center; }
.stepper .bar { margin-bottom: 8px; }
.stepper span { font-size: 13px; color: var(--ink-4); font-weight: 600; }
.stepper .on span { color: var(--ink); }
.foot { margin-top: 64px; padding-top: 24px; border-top: 1px solid var(--line); font-size: 14px; color: var(--ink-4); line-height: 1.7; }

[class*="st-key-sticky_"] { position: sticky; top: 132px; }
@media (max-width: 640px) { [class*="st-key-sticky_"] { position: static; } }
.st-key-topbar [data-testid="stHorizontalBlock"] { flex-wrap: nowrap !important; }
.st-key-topbar [data-testid="stColumn"] { min-width: 0 !important; width: auto !important; flex: 1 1 auto !important; }
.st-key-topbar [data-testid="stColumn"]:last-child { flex: 0 0 auto !important; }

/* ---------- 혼디 2차: 히어로·벤토·라이브 위젯 ---------- */
@keyframes up { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: none; } }
.card, .stat, .hero-card, .bento > div { animation: up .45s ease both; }
.card { transition: transform .18s ease, box-shadow .18s ease, border-color .18s ease; }
.card.lift:hover { transform: translateY(-3px); box-shadow: 0 12px 28px rgba(25,31,40,.08); border-color: var(--brand-weak-2); }
.hero-card { position: relative; overflow: hidden; border-radius: 32px; padding: 56px 48px 64px; margin: 28px 0 12px;
  background: radial-gradient(120% 140% at 100% 0%, #FFB36B 0%, #FF8A2B 35%, #EE5A00 75%, #D94A00 100%); color: #fff; }
.eyebrow { display: inline-flex; gap: 6px; align-items: center; font-size: 15px; font-weight: 600; padding: 7px 14px; border-radius: 999px; }
.hero-card .eyebrow { background: rgba(255,255,255,.22); color: #fff; position: relative; z-index: 2; }
.hero-card h1 { color: #fff !important; font-size: clamp(32px, 5.4vw, 56px) !important; line-height: 1.18 !important; font-weight: 800 !important; margin: 18px 0 14px !important; padding: 0 !important; position: relative; z-index: 2; }
.hero-card p { color: rgba(255,255,255,.94); font-size: clamp(16px, 2vw, 19px); line-height: 1.6; margin: 0; max-width: 560px; position: relative; z-index: 2; }
.hero-card svg.scene { position: absolute; left: 0; right: 0; bottom: 0; width: 100%; height: 70%; z-index: 1; pointer-events: none; }
.hero-card .hero-stats { display: flex; gap: 28px; margin-top: 28px; position: relative; z-index: 2; flex-wrap: wrap; }
.hero-card .hero-stats b { display: block; font-size: 26px; font-weight: 800; }
.hero-card .hero-stats span { font-size: 14px; opacity: .9; }
@media (max-width: 640px) { .hero-card { padding: 36px 22px 120px; border-radius: 24px; } .hero-card svg.scene { width: 100%; } }
.bento { display: grid; grid-template-columns: repeat(4, 1fr); grid-auto-rows: minmax(150px, auto); gap: 14px; }
.bento > div { border-radius: 24px; padding: 24px; position: relative; overflow: hidden; }
.bento .b-lg { grid-column: span 2; grid-row: span 2; background: var(--ink); color: #fff; }
.bento .b-lg h4, .bento .b-lg p { color: #fff !important; } .bento .b-lg p { opacity: .8; }
.bento .b-md { grid-column: span 2; background: var(--brand-weak); }
.bento .b-sm { grid-column: span 1; background: var(--fill); }
.bento h4 { font-size: 20px !important; margin: 14px 0 6px !important; padding: 0 !important; }
.bento p { font-size: 15px; color: var(--ink-3); margin: 0; line-height: 1.55; }
.bento .ico { width: 44px; height: 44px; border-radius: 14px; display: grid; place-items: center; background: #fff; color: var(--brand); }
.bento .b-lg .ico { background: var(--brand); color: #fff; }
.bento .big { font-size: 44px; font-weight: 800; letter-spacing: -0.04em; margin-top: 18px; }
@media (max-width: 900px) { .bento { grid-template-columns: repeat(2, 1fr); } .bento .b-lg { grid-row: span 1; } }
@media (max-width: 560px) { .bento { grid-template-columns: 1fr; } .bento > div { grid-column: span 1 !important; } }
.live { display: inline-flex; align-items: center; gap: 6px; font-size: 13px; font-weight: 700; color: var(--good); background: var(--good-weak); border-radius: 999px; padding: 4px 10px; }
.live i { width: 8px; height: 8px; border-radius: 50%; background: var(--good); animation: blink 1.4s infinite; }
.live.off { color: var(--ink-3); background: var(--fill); } .live.off i { background: var(--ink-4); animation: none; }
@keyframes blink { 50% { opacity: .25; } }
.vital { padding: 18px 18px 12px; border-radius: 20px; background: #fff; border: 1px solid var(--line); height: 100%; }
.vital .k { font-size: 14px; color: var(--ink-3); font-weight: 600; display: flex; align-items: center; gap: 6px; }
.vital .v { font-size: 30px; font-weight: 800; color: var(--ink); letter-spacing: -0.03em; line-height: 1.2; margin-top: 4px; }
.vital .v small { font-size: 15px; color: var(--ink-4); font-weight: 600; margin-left: 2px; }
.vital svg.spark { display: block; width: 100%; height: 40px; margin-top: 6px; }
.vital .k svg { flex: none; }
.vital .s { font-size: 13px; font-weight: 600; margin-top: 2px; }
.device { border: 2px solid var(--line); border-radius: 20px; padding: 20px; background: #fff; text-align: left; }
.device.on { border-color: var(--brand); background: var(--brand-weak); }
.perm { display: flex; gap: 12px; align-items: center; padding: 12px 0; border-bottom: 1px solid var(--line); font-size: 16px; color: var(--ink-2); }
.chat { display: flex; flex-direction: column; gap: 8px; padding: 6px 0; }
.bubble { max-width: 78%; padding: 10px 14px; border-radius: 18px; font-size: 16px; line-height: 1.5; }
.bubble.me { align-self: flex-end; background: var(--brand-strong); color: #fff; border-bottom-right-radius: 6px; }
.bubble.them { align-self: flex-start; background: var(--fill); color: var(--ink); border-bottom-left-radius: 6px; }
.bubble.sys { align-self: center; background: transparent; color: var(--ink-4); font-size: 13px; padding: 2px; }
.bubble time { display: block; font-size: 12px; opacity: .7; margin-top: 2px; }
.flow { display: flex; gap: 0; margin: 10px 0 2px; }
.flow > div { flex: 1; position: relative; text-align: center; font-size: 13px; color: var(--ink-4); font-weight: 600; padding-top: 30px; }
.flow > div:before { content: ""; position: absolute; top: 10px; left: 50%; width: 20px; height: 20px; margin-left: -10px; border-radius: 50%; background: var(--fill); border: 2px solid var(--line-2); z-index: 1; }
.flow > div:after { content: ""; position: absolute; top: 19px; left: -50%; width: 100%; height: 3px; background: var(--line); }
.flow > div:first-child:after { display: none; }
.flow > div.done { color: var(--ink-2); } .flow > div.done:before { background: var(--brand); border-color: var(--brand); } .flow > div.done:after { background: var(--brand); }
.flow > div.now { color: var(--ink); } .flow > div.now:before { background: #fff; border: 5px solid var(--brand); }  .flow > div.now:after { background: var(--brand); }
.alert-item { display: flex; gap: 12px; padding: 12px 0; border-bottom: 1px solid var(--line); align-items: flex-start; }
.alert-item:last-child { border-bottom: 0; }
.alert-item .dot { width: 10px; height: 10px; border-radius: 50%; margin-top: 7px; flex: none; }
.receipt .row .t { font-size: 16px; }
.countdown { font-size: 56px; font-weight: 800; color: var(--bad); text-align: center; letter-spacing: -0.04em; }

hr { border-color: var(--line) !important; }
</style>
"""

_LARGE = """<style>
[data-testid="stMainBlockContainer"] { zoom: 1.15; }
</style>"""

_CONTRAST = """<style>
:root { --ink-2: #191F28; --ink-3: #2B323C; --ink-4: #3D4652; --line: #8B95A1; --line-2: #6B7684; --brand-text: #0F4FB3; --fill: #E5E8EB; }
.card, .tl-card, .stat { border: 1.5px solid #6B7684 !important; }
</style>"""


def apply_theme() -> None:
    # 빈 줄이 있으면 마크다운이 <style> 블록을 중간에 끊으므로 한 줄씩 붙여 넣습니다
    css = _BASE
    if st.session_state.get("a11y_large"):
        css += _LARGE
    if st.session_state.get("a11y_contrast"):
        css += _CONTRAST
    st.markdown(tidy(css), unsafe_allow_html=True)
