#!/usr/bin/env python3
"""Generate a self-contained, professionally styled standalone HTML from a Markdown file.
- Renders ```mermaid blocks to PNG via mmdc and embeds them (base64 via pandoc --embed-resources)
- Fixed sidebar TOC with active-section highlighting + back-to-top
Usage: htmlgen.py input.md output.html "Document Title" "Subtitle"
"""
import re, sys, os, subprocess, tempfile, hashlib

TEMPLATE_DIR = os.path.dirname(os.path.abspath(__file__))

def render_mermaid(md: str, workdir: str) -> str:
    def rep(m):
        src = m.group(1)
        h = hashlib.md5(src.encode()).hexdigest()[:10]
        mmd = os.path.join(workdir, f"{h}.mmd")
        png = os.path.join(workdir, f"{h}.png")
        if not os.path.exists(png):
            open(mmd, "w").write(src)
            r = subprocess.run(["mmdc", "-i", mmd, "-o", png, "-q", "-b", "white", "-s", "2"],
                               capture_output=True, text=True)
            if r.returncode != 0:
                raise SystemExit(f"mermaid render failed for block {h}: {r.stderr[:500]}")
        return f"![diagram]({png}){{.diagram}}"
    return re.sub(r"```mermaid\n(.*?)```", rep, md, flags=re.S)

def main():
    src, out, title = sys.argv[1], sys.argv[2], sys.argv[3]
    subtitle = sys.argv[4] if len(sys.argv) > 4 else ""
    md = open(src).read()
    md = re.sub(r"(?m)^# .*\n", "", md, count=1)  # drop first H1; template renders title
    workdir = tempfile.mkdtemp(prefix="mmd_")
    md = render_mermaid(md, workdir)
    tmp = os.path.join(workdir, "in.md")
    open(tmp, "w").write(md)
    cmd = ["pandoc", tmp, "-f", "markdown+pipe_tables", "-t", "html5",
           "--standalone", "--embed-resources", "--toc", "--toc-depth=3",
           "--template", os.path.join(TEMPLATE_DIR, "template.html"),
           "--metadata", f"pagetitle={title}", "--metadata", f"doctitle={title}",
           "--metadata", f"subtitle={subtitle}",
           "-o", out]
    subprocess.run(cmd, check=True)
    print(f"wrote {out} ({os.path.getsize(out)//1024} KB)")

if __name__ == "__main__":
    main()
