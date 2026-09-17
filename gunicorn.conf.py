# LINE image/PDF analysis can legitimately exceed Gunicorn's 30s default while
# waiting for the upstream AI response. Keep the worker alive long enough for
# the existing media pipeline to persist the analysis and reply.
timeout = 120
graceful_timeout = 30
