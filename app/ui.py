from fastapi.responses import HTMLResponse


def page_html() -> HTMLResponse:
    return HTMLResponse(content="""
<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Shodh Arena</title></head>
<body style="font-family:system-ui;margin:40px;color:#172033"><h1>Shodh Contest Platform</h1><p>This interface placeholder is intended to be replaced by app/interface.py.</p></body>
</html>
""
)
