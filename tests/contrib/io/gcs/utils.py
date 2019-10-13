def matcher(r1, r2):
    if r2.uri != r1.uri:
        return False
    if r1.method != r2.method:
        return False
    if r1.method != "POST" and r1.body != r2.body:
        return False
    if r1.method == "POST":
        try:
            r1_body, r2_body = r1.body.decode(), r2.body.decode()
            r1_body = r1_body.replace("--===============[0-9]+==\r\ncontent-type", "")
            r2_body = r1_body.replace("--===============[0-9]+==\r\ncontent-type", "")

            return r1_body == r2_body
        except:
            pass
        r1q = (r1.body or b"").split(b"&")
        r2q = (r2.body or b"").split(b"&")
        for q in r1q:
            if b"secret" in q or b"token" in q:
                continue
            if q not in r2q:
                return False
    else:
        for key in ["Content-Length", "Content-Type", "Range"]:
            if key in r1.headers and key in r2.headers:
                if r1.headers.get(key, "") != r2.headers.get(key, ""):
                    return False
    return True