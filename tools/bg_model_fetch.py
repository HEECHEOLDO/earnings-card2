# 시험용 — 배경 지우기(imgly) 모델 파일을 받아 하나로 합친다 (폰 '빠름' 결과 재현용)
import json, urllib.request, sys
B = "https://staticimgly.com/@imgly/background-removal-data/1.5.8/dist/"
res = json.load(urllib.request.urlopen(B + "resources.json"))
for k in ("/models/isnet_quint8", "/models/isnet_fp16"):
    r = res[k]
    with open(k.split("/")[-1] + ".onnx", "wb") as f:
        for c in r["chunks"]:
            f.write(urllib.request.urlopen(B + c["hash"]).read())
    print(k, r.get("size"), len(r["chunks"]))
