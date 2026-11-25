from pathlib import Path
from html.parser import HTMLParser

class HeaderButtons(HTMLParser):
    def __init__(self):
        super().__init__(); self.in_header=False; self.header=[]; self.other=[]
    def handle_starttag(self, tag, attrs):
        if tag=='header': self.in_header=True
        if tag=='button': (self.header if self.in_header else self.other).append(dict(attrs))
    def handle_endtag(self, tag):
        if tag=='header': self.in_header=False

def test_header_no_legacy_json_export():
    p=HeaderButtons(); p.feed((Path(__file__).resolve().parents[1]/'app/index.html').read_text(encoding='utf-8'))
    assert not any(x.get('onclick')=="download('json')" for x in p.header)
    assert {'rescan()', 'openLocalSettings()', 'openAbout()'} <= {x.get('onclick') for x in p.header}
    assert not {"download('json')", "download('csv')"} & {x.get('onclick') for x in p.other}


def test_no_legacy_text_export_and_native_controls_retained():
    html=(Path(__file__).resolve().parents[1]/"app/index.html").read_text(encoding="utf-8")
    p=HeaderButtons(); p.feed(html)
    actions={x.get("onclick") for x in p.header+p.other}
    assert "exportPrompts()" not in actions
    assert "function exportPrompts(" not in html
    assert {"openGenerator()", "openEditor()", "openImageEditor()", "downloadGeneratorBatchManifest()", "exportActiveRefPack()"} <= actions
