"""Hit rate of /ask on faq_tests.txt, against the website as built from this repo (no network, no Discord).

    python3 faq_eval.py [--words]      (--words: without the embedding model)
Needs fastembed in the Python running it for the model scores (pip install fastembed).
"""
import asyncio, glob, os, sys, tempfile, subprocess
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import faq

SITE_SRC = os.path.join(HERE, "..", "..", "marketing", "site")


def local_site():
    out = tempfile.mkdtemp()
    subprocess.run([sys.executable, "build.py", out], cwd=SITE_SRC, check=True, stdout=subprocess.DEVNULL)
    pages = sorted(glob.glob(os.path.join(out, "**", "index.html"), recursive=True), key=lambda p: ("/faq/" not in p, p))
    qas, seen = [], set()
    for p in pages:
        if "/news/" in p: continue
        url = faq.SITE + "/" + os.path.relpath(os.path.dirname(p), out).replace(".", "").strip("/") + "/"
        for qa in faq._site_from_html(open(p, encoding="utf-8").read(), url):
            if qa["q"].lower() not in seen: seen.add(qa["q"].lower()); qas.append(qa)
    return qas


def main():
    if "--words" not in sys.argv: faq._load_model()
    faq._build(local_site())
    tests = next((a for a in sys.argv[1:] if a.endswith(".txt")), "faq_tests.txt")
    rows = [l.split(" | ", 1) for l in open(os.path.join(HERE, tests), encoding="utf-8") if l.strip() and not l.startswith("#")]
    right = guess = wrong = 0
    for q, want in rows:
        q, want = q.strip(), want.strip()
        e, score, _ = faq.match(q)
        if want == "-":
            ok = e is None or score < faq.ANSWER
            tag = "ok " if ok else "BAD"
            right += ok; wrong += not ok
        else:
            hit = e is not None and any(w.strip().lower() in e["q"].lower() for w in want.split("||"))
            if hit and score >= faq.ANSWER: tag = "ok "; right += 1
            elif hit: tag = "gss"; guess += 1
            else: tag = "BAD"; wrong += 1
        if tag != "ok " or "-v" in sys.argv:
            print(f"{tag} {score:.2f}  {q}  ->  {e['q'] if e else None}   (want: {want})")
    n = len(rows)
    print(f"\n{n} questions: {right} right ({right / n:.0%}), {guess} right but as a 'best guess' ({guess / n:.0%}), {wrong} wrong ({wrong / n:.0%})")


if __name__ == "__main__":
    main()
