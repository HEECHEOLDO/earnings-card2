#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""시가총액 카드 제목 왼쪽에 아이콘을 넣는다.

  python3 patch_mcap_emoji.py

  코스피 · 코스닥 · 국내주식   태극기 (이모지가 아니라 직접 그린 그림 — 윈도우에서도 똑같이 보임)
  업종                        업종마다 정해 둔 이모지 (아래 UPJONG)
  테마                        이름에 든 낱말로 고른 이모지 (아래 THEME, 위에서부터 먼저 맞는 것)
                              어디에도 안 맞으면 📈
  왼쪽 칸에 '아이콘' 체크박스가 생겨서 끌 수도 있다.
고칠 때는 mcap.html 안 'MCAP_EMOJI' 표를 고치면 된다. 두 번 돌려도 괜찮다.
"""
import json
import sys

FN = "mcap.html"
MARK = "MCAP_EMOJI"

# 업종 — 네이버 이름(띄어쓰기 빼고) : 이모지
UPJONG = {
    "전기제품": "🔌", "화학": "🧪", "에너지장비및서비스": "🛢️", "비철금속": "🥈", "IT서비스": "💻",
    "백화점과일반상점": "🏬", "자동차": "🚗", "철강": "🏗️", "기계": "⚙️", "통신장비": "📡",
    "전자장비와기기": "🔋", "건강관리기술": "🩺", "방송과엔터테인먼트": "📺", "제약": "💊", "생물공학": "🧬",
    "전기장비": "⚡", "판매업체": "📦", "반도체와반도체장비": "💾", "자동차부품": "🔧", "항공사": "✈️",
    "석유와가스": "⛽", "우주항공과국방": "🚀", "출판": "📚", "전기유틸리티": "⚡", "건설": "🏗️",
    "핸드셋": "📱", "창업투자": "🌱", "생명보험": "🛡️", "건강관리장비와용품": "🩻", "복합유틸리티": "🔥",
    "복합기업": "🏢", "손해보험": "🛡️", "도로와철도운송": "🚆", "건강관리업체및서비스": "🏥",
    "무역회사와판매업체": "🚢", "게임엔터테인먼트": "🎮", "생명과학도구및서비스": "🔬", "가스유틸리티": "🔥",
    "증권": "📈", "디스플레이장비및부품": "🖥️", "포장재": "📦", "해운사": "🚢", "전자제품": "📺",
    "양방향미디어와서비스": "🌐", "건축자재": "🧱", "광고": "📣", "건축제품": "🚪",
    "항공화물운송과물류": "🚚", "교육서비스": "🎓", "호텔,레스토랑,레저": "🏨", "전문소매": "🛍️",
    "다각화된소비자서비스": "🧾", "상업서비스와공급품": "🗂️", "음료": "🥤", "무선통신서비스": "📶",
    "인터넷과카탈로그소매": "🛒", "식품": "🍜", "디스플레이패널": "🖥️", "기타": "📊", "소프트웨어": "💿",
    "다각화된통신서비스": "☎️", "부동산": "🏠", "종이와목재": "🪵", "가구": "🛋️", "문구류": "✏️",
    "섬유,의류,신발,호화품": "👗", "운송인프라": "🛣️", "레저용장비와제품": "⛳", "담배": "🚬", "조선": "🛳️",
    "은행": "🏦", "화장품": "💄", "가정용기기와용품": "🧺", "카드": "💳", "컴퓨터와주변기기": "🖱️",
    "식품과기본식료품소매": "🛒", "사무용전자제품": "🖨️", "가정용품": "🧴", "기타금융": "💰",
}

# 테마 — [이름에 들어 있는 낱말(정규식), 이모지]. 위에서부터 먼저 맞는 것을 쓴다.
THEME = [
    ["화폐|금융자동화|ATM|키오스크", "💵"],
    ["가상화폐|비트코인|블록체인|NFT|STO|토큰|스테이블", "🪙"],
    ["결제|핀테크|페이|카드", "💳"],
    ["밸류업|배당|자사주|지주사|지배구조", "💰"],
    ["은행|금융", "🏦"], ["증권", "📈"], ["보험", "🛡️"],
    ["S7|대형주", "🏆"],
    ["HBM|CXL|PIM|뉴로모픽|반도체|파운드리|웨이퍼|메모리|시스템반도체|유리기판|칩", "💾"],
    ["휴머노이드|로봇", "🤖"],
    ["AI|인공지능|챗봇|GPT|LLM|딥러닝|온디바이스", "🧠"],
    ["양자", "⚛️"],
    ["데이터센터|클라우드|빅데이터|서버", "☁️"],
    ["보안|해킹|랜섬", "🔒"],
    ["메타버스|가상현실|증강현실|VR|AR|XR|MR", "🥽"],
    ["전고체|나트륨|LFP|2차전지|배터리|리튬|폐배터리|ESS|전해", "🔋"],
    ["충전", "🔌"],
    ["전기차|자율주행|자동차|타이어|모빌리티", "🚗"],
    ["수소", "💧"],
    ["태양광", "☀️"], ["풍력", "🌬️"],
    ["원자력|원전|SMR|핵융합|우라늄", "☢️"],
    ["전력|전선|변압기|송전|스마트그리드|초전도", "⚡"],
    ["탄소|CCUS|온실가스|친환경|기후|재활용|폐기물|플라스틱", "♻️"],
    ["석유|정유|가스|LNG|LPG|셰일|유가", "⛽"],
    ["우주|위성|누리호|발사체", "🛰️"],
    ["방위|방산|전쟁|테러|국방|K-방산", "🛡️"],
    ["드론|UAM|도심항공", "🚁"],
    ["항공|공항|저가항공|LCC", "✈️"],
    ["조선|선박|해운|해양|항만", "🚢"],
    ["철도|지하철|GTX|고속터미널|고속버스", "🚆"],
    ["물류|택배|운송", "🚚"],
    ["건설|재건|재개발|리모델링|시멘트|레미콘|건자재|SOC|부동산|리츠|모듈러", "🏗️"],
    ["철강|비철|구리|니켈|알루미늄|희토류|희귀금속|금속|아연|광물|코발트", "🔩"],
    ["금값|금시세|^금$|금 관련", "🥇"],
    ["화학|석유화학|페인트|비료", "🧪"],
    ["코로나|진단|백신|음압|마스크|전염|감염|엠폭스|원숭이두창|독감", "🦠"],
    ["비만|당뇨", "⚖️"],
    ["치매|뇌|파킨슨", "🧠"],
    ["줄기세포|유전자|바이오|mRNA|세포|항암|면역|CMO|CDMO|신약|펩타이드|ADC", "🧬"],
    ["제약|의약|치료제|복제약|바이오시밀러|원료의약", "💊"],
    ["의료|병원|헬스케어|임플란트|치아|미용기기|보톡스|필러|진료|원격", "🏥"],
    ["화장품|뷰티|미용", "💄"],
    ["5G|6G|통신|LTE|안테나", "📶"],
    ["스마트폰|폴더블|아이폰|갤럭시|휴대폰", "📱"],
    ["OLED|LED|디스플레이|LCD", "🖥️"],
    ["카메라|렌즈|광학", "📷"],
    ["PCB|기판|MLCC|전자부품|부품", "🔧"],
    ["게임|e스포츠|PC방", "🎮"],
    ["웹툰|만화|캐릭터|애니", "📖"],
    ["엔터|K-POP|아이돌|음원|음반|음악|공연|연예", "🎤"],
    ["영화|드라마|OTT|콘텐츠|미디어|방송", "🎬"],
    ["광고|마케팅", "📣"],
    ["여행|관광|면세|호텔|리조트|카지노|크루즈", "🧳"],
    ["골프|캠핑|레저|스포츠|자전거|낚시|스키", "⛳"],
    ["교육|학원|입시|에듀", "🎓"],
    ["출산|영유아|육아|아기|유아|저출산", "🍼"],
    ["반려동물|펫|동물", "🐶"],
    ["음식료|식품|라면|과자|음료|커피|우유|유가공|HMR|간편식|K-푸드", "🍜"],
    ["주류|맥주|소주|와인|위스키", "🍺"],
    ["담배|전자담배|마리화나|대마", "🚬"],
    ["농업|스마트팜|종자|사료|비료", "🌾"],
    ["수산|어업|참치|김 ", "🐟"],
    ["육계|닭|돼지|축산|구제역|조류독감|AI\\(조류\\)|아프리카돼지열병", "🐔"],
    ["수자원|상하수도|정수|가뭄|홍수|장마", "💧"],
    ["미세먼지|황사|공기청정", "😷"],
    ["폭염|에어컨|냉각|냉방", "🌡️"],
    ["난방|한파|보일러", "🔥"],
    ["지진|재난|재해|안전", "⛑️"],
    ["남북|대북|개성|북한|통일", "🕊️"],
    ["우크라이나|러시아|중동|이스라엘|사우디|네옴", "🌍"],
    ["중국|일본|미국|인도|베트남|인도네시아|트럼프|바이든|대선|정치|정책|국회|선거|윤석열|이재명|한동훈", "🏛️"],
    ["편의점|백화점|홈쇼핑|이커머스|온라인쇼핑|유통|쇼핑|소매", "🛒"],
    ["의류|패션|섬유|신발|명품", "👗"],
    ["가구|인테리어|침대", "🛋️"],
    ["제지|종이|목재|골판지", "📦"],
    ["포장|택배|박스", "📦"],
    ["소프트웨어|SW|SaaS|ERP|솔루션|IT", "💻"],
    ["인터넷|포털|플랫폼|SNS|검색", "🌐"],
    ["사물인터넷|IoT|스마트홈|스마트시티|스마트팩토리|자동화|공작기계|3D", "🏭"],
    ["기계|건설기계|농기계|장비", "⚙️"],
    ["가전|TV|냉장고|세탁기", "📺"],
    ["시스템|정보", "💻"],
    ["스팩|SPAC", "📄"],
    ["신규상장|공모|IPO", "🔔"],
]

JS = """
  // ── 제목 왼쪽 아이콘 (MCAP_EMOJI) ── 표를 고치면 바로 반영된다
  var MCAP_EMOJI = { upjong: %s,
    theme: %s, other: '📈' };
  function mcapIcon(mk, gg) {
    if (mk === 'kospi' || mk === 'kosdaq' || mk === 'all') return 'KR';
    if (!gg) return '';
    var key = String(gg.name || '').replace(/\\s/g, '');
    if (mk === 'industry' && MCAP_EMOJI.upjong[key]) return MCAP_EMOJI.upjong[key];
    var names = [gg.name || '', gg.short || ''];
    for (var i = 0; i < MCAP_EMOJI.theme.length; i++) {
      var re = new RegExp(MCAP_EMOJI.theme[i][0]);
      if (re.test(names[0]) || re.test(names[1])) return MCAP_EMOJI.theme[i][1];
    }
    return MCAP_EMOJI.other;
  }
  // 태극기 — 높이 h, 왼쪽 위 (x, y)
  function drawTaegeuk(c, x, y, h) {
    var w = h * 1.5, cx = x + w / 2, cy = y + h / 2, r = h / 4, a = Math.atan2(2, 3);
    c.save();
    c.beginPath(); if (c.roundRect) c.roundRect(x, y, w, h, h * 0.08); else c.rect(x, y, w, h);
    c.fillStyle = '#ffffff'; c.fill(); c.lineWidth = Math.max(1, h * 0.025); c.strokeStyle = '#D9D6CE'; c.stroke();
    c.translate(cx, cy); c.rotate(a);
    c.beginPath(); c.arc(0, 0, r, 0, Math.PI * 2); c.fillStyle = '#0047A0'; c.fill();
    c.beginPath(); c.arc(0, 0, r, Math.PI, Math.PI * 2); c.fillStyle = '#CD2E3A'; c.fill();
    c.beginPath(); c.arc(-r / 2, 0, r / 2, 0, Math.PI * 2); c.fillStyle = '#CD2E3A'; c.fill();
    c.beginPath(); c.arc(r / 2, 0, r / 2, 0, Math.PI * 2); c.fillStyle = '#0047A0'; c.fill();
    c.rotate(-a);
    // 괘: 건(☰) 왼쪽 위, 감(☵) 오른쪽 위, 리(☲) 왼쪽 아래, 곤(☷) 오른쪽 아래
    var t = h / 24, g = h / 48, L = h / 4, d = r + h / 8 + (3 * t + 2 * g) / 2;
    [[-3, -2, [1, 1, 1]], [3, -2, [0, 1, 0]], [-3, 2, [1, 0, 1]], [3, 2, [0, 0, 0]]].forEach(function (k) {
      var ang = Math.atan2(k[1], k[0]);
      c.save(); c.rotate(ang); c.translate(d, 0); c.fillStyle = '#000000';
      k[2].forEach(function (solid, i) {
        var bx = -(3 * t + 2 * g) / 2 + i * (t + g);
        if (solid) c.fillRect(bx, -L / 2, t, L);
        else { c.fillRect(bx, -L / 2, t, (L - g) / 2); c.fillRect(bx, g / 2, t, (L - g) / 2); }
      });
      c.restore();
    });
    c.restore();
    return w;
  }
  // 아이콘을 그리고 그 폭(간격 포함)을 돌려준다. ns = 제목 글자 크기, y = 제목 기준선
  function drawIcon(c, icon, x, y, ns, dry) {
    if (!icon) return 0;
    var mid = y - ns * 0.37;
    if (icon === 'KR') { var h = ns * 0.66; if (!dry) drawTaegeuk(c, x, mid - h / 2, h); return h * 1.5 + ns * 0.24; }
    c.save(); c.font = Math.round(ns * 0.86) + 'px "Apple Color Emoji","Segoe UI Emoji","Noto Color Emoji",sans-serif';
    var w = c.measureText(icon).width;
    if (!dry) { c.textBaseline = 'middle'; c.textAlign = 'left'; c.fillText(icon, x, mid + ns * 0.02); }
    c.restore();
    return w + ns * 0.2;
  }
"""

REPL = [
    ("아이콘 함수", "  function foot(footY) {", None),
    ("아이콘 고르기 (자동 문구)",
     "    window.MCAP_FOOT = a ? a[0] + '년 ' + (+a[1]) + '월 ' + (+a[2]) + '일 기준' : '';",
     "    window.MCAP_FOOT = a ? a[0] + '년 ' + (+a[1]) + '월 ' + (+a[2]) + '일 기준' : '';\n"
     "    window.MCAP_ICON = mcapIcon(mk, (mk === 'industry' || mk === 'theme') ? gg : null);"),
    ("제목 크기 — 아이콘 폭만큼 줄이기",
     "var ns = fit(title, 900, 92, 36, W), y = S.top + ns * 0.86;",
     "var ICON = (document.getElementById('chk-icon') || {}).checked === false ? '' : (window.MCAP_ICON || '');\n"
     "    var ns = 92; ctx.font = font(900, ns);\n"
     "    while (ns > 36 && ctx.measureText(title).width + drawIcon(ctx, ICON, 0, 0, ns, true) > W) { ns -= 1; ctx.font = font(900, ns); }\n"
     "    var y = S.top + ns * 0.86, XT = X0 + drawIcon(ctx, ICON, X0, S.top + ns * 0.86, ns);\n"
     "    ctx.fillStyle = T.ink; ctx.textBaseline = 'alphabetic'; ctx.textAlign = 'left';"),
    ("제목 앞부분 위치", "ctx.fillText(tm[1], X0, y);", "ctx.fillText(tm[1], XT, y);"),
    ("제목 '시가총액' 위치", "ctx.fillText(tm[2], X0 + tw, y);", "ctx.fillText(tm[2], XT + tw, y);"),
    ("제목 (나머지) 위치", "ctx.fillText(title, X0, y); }", "ctx.fillText(title, XT, y); }"),
    ("아이콘 체크박스",
     '      <label class="f" for="title">제목</label>',
     '      <label style="display:flex;align-items:center;gap:6px;margin:6px 0"><input type="checkbox" id="chk-icon" checked> 제목 왼쪽 아이콘 (태극기·이모지)</label>\n'
     '      <label class="f" for="title">제목</label>'),
    ("체크박스를 바꾸면 다시 그리기",
     "  document.getElementById('grp').addEventListener('change', function () { fill(); draw(); });",
     "  document.getElementById('grp').addEventListener('change', function () { fill(); draw(); });\n"
     "  document.getElementById('chk-icon').addEventListener('change', function () { draw(); });"),
]


def main():
    try:
        s = open(FN, encoding="utf-8").read()
    except OSError:
        print("!! %s 가 없습니다. fincard 폴더에서 실행하세요." % FN)
        sys.exit(1)
    if MARK in s:
        print("  그대로  %s  이미 고쳐짐" % FN)
        return
    bad = [lab for lab, a, _ in REPL if s.count(a) != 1]
    if bad:
        print("!! %s 이 예상과 달라 고치지 않았습니다. 못 찾은 자리:" % FN)
        for b in bad:
            print("   - " + b)
        print("   patch_mcap_c.py 를 먼저 돌렸는지 확인하고, 그래도 안 되면 mcap.html 을 보내 주세요.")
        sys.exit(1)
    js = JS % (json.dumps(UPJONG, ensure_ascii=False), json.dumps(THEME, ensure_ascii=False))
    for lab, a, b in REPL:
        s = s.replace(a, js.lstrip("\n") + "\n" + a if b is None else b)
    open(FN, "w", encoding="utf-8").write(s)
    print("  고침    %s  — 제목 왼쪽 아이콘 (시장 태극기 · 업종·테마 이모지)" % FN)


if __name__ == "__main__":
    main()
