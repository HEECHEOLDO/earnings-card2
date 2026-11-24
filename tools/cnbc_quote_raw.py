"""시험: CNBC 시세 원문 필드 보기 (CODES 에 쉼표로 기호)"""
import json, os, sys, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from collect_chart_us import get
syms = (os.environ.get("CODES") or ".SPX,SPY").split(",")
url = ("https://quote.cnbc.com/quote-html-webservice/restQuote/symbolType/symbol?symbols=%s"
       "&requestMethod=itv&noform=1&partnerId=2&fund=1&exthrs=0&output=json" % urllib.parse.quote("|".join(syms), safe="|."))
q = ((json.loads(get(url)).get("FormattedQuoteResult") or {}).get("FormattedQuote")) or []
for x in (q if isinstance(q, list) else [q]):
    print({k: v for k, v in x.items() if not isinstance(v, (dict, list))})
