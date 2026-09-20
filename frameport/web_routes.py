"""Shared, explicit document routes. Unknown API/static paths never get HTML."""
from fastapi import HTTPException
from fastapi.responses import FileResponse
from .config import ROOT

APP_CSP = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self'; connect-src 'self'; frame-src 'self'; object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'"
DOCUMENT_ROUTES = ('/', '/convert', '/projects', '/settings', '/login', '/docs')
PROJECT_TABS = ('review', 'content', 'source', 'verify', 'export')


def install_documents(app):
    async def document():
        return FileResponse(ROOT / 'web' / 'index.html', headers={
            'Cache-Control': 'no-store', 'Content-Security-Policy': APP_CSP,
            'X-Content-Type-Options': 'nosniff', 'Referrer-Policy': 'no-referrer',
        })
    for path in DOCUMENT_ROUTES:
        app.add_api_route(path, document, methods=['GET'], include_in_schema=False)

    @app.get('/projects/{ident}', include_in_schema=False)
    @app.get('/projects/{ident}/{tab}', include_in_schema=False)
    async def project_document(ident: str, tab: str = 'review'):
        import re
        if not re.fullmatch(r'[0-9a-f]{32}', ident) or tab not in PROJECT_TABS:
            raise HTTPException(404, 'Page not found')
        return await document()
