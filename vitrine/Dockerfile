# Vitrine: read-only weergave van één verwerkt boek.
#
# Oorspronkelijk opgezet om via de OpenAI-API te zoeken, zodat er geen model op
# de server hoefde. Dat account bleek zonder tegoed, dus draait het lokale model
# nu in de container zelf. Zwaarder dan de API-route, maar zelfstandig: geen
# externe afhankelijkheid en geen kosten per zoekopdracht. Het model draait op de
# processor via ONNX; geen GPU nodig.
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# De lichte importketen die de zoeklaag nodig heeft. De zware kant van de
# pijplijn (OCR, PDF) blijft er bewust buiten.
COPY kennisbank/ kennisbank/
COPY vitrine.py boek_mcp.py converteer_openai.py ./
COPY templates/ templates/

# Het embedmodel in de image bakken, zodat de container bij de start niets hoeft
# te downloaden en ook zonder internet werkt. Dit is dezelfde rug waarmee de
# kennisbank is gebouwd, dus corpus en zoekvraag blijven vergelijkbaar.
ENV EMBED_BACKEND=fastembed \
    FASTEMBED_CACHE_PATH=/app/.modelcache \
    HF_HUB_DISABLE_SYMLINKS_WARNING=1
RUN python -c "from fastembed import TextEmbedding; \
    TextEmbedding('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2', \
    cache_dir='/app/.modelcache'); print('model gecachet')"

ENV KB_PAD=/data/kennisbank.db \
    RAPPORT_PAD=/data/rapport.json \
    PORT=3025

EXPOSE 3025

# Eén worker met twee threads: weinig gelijktijdige bezoekers, en het model plus
# de zoekmatrix staan per proces in het geheugen.
#
# GEEN --preload, en dat is geen detail. Met preload importeert de MASTER de
# app, en daar start dan ook de opwarmthread; de worker is een fork waarin die
# thread niet meedraait, dus het klaar-sein werd daar nooit gezet en de
# wachtpagina bleef eeuwig staan. Zonder preload bindt de master de poort
# meteen en importeert de worker zelf, met zijn eigen opwarmthread.
CMD ["gunicorn", "--bind", "0.0.0.0:3025", "--workers", "1", "--threads", "2", \
     "--timeout", "120", "vitrine:app"]
