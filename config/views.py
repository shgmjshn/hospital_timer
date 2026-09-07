from django.http import HttpResponse


def healthz(_request):
    """Render のポート検出・ヘルスチェック用。DB には触れない。"""
    return HttpResponse("ok", content_type="text/plain")
