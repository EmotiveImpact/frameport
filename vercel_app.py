"""Stateless Vercel entrypoint. No ephemeral database or background worker."""
from frameport.gateway import create_gateway
app = create_gateway()
