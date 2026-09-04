# Publieke demo achter elevaitnv.com/demo.
#
# Het embedmodel zit in de image, zodat de container bij de start niets hoeft
# te downloaden en ook zonder internet werkt. Geen OCR-afhankelijkheden: de
# demo bouwt niets, hij doorzoekt een kennisbank die wij vooraf hebben gemaakt.
#
# De kennisbank zelf zit NIET in de image. Die wordt als volume aangekoppeld op
# /app/data, zodat een ander demodocument geen herbouw vraagt.
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY kennisbank/ kennisbank/
COPY demo.py waarom.py ./
COPY templates/ templates/

ENV EMBED_BACKEND=fastembed \
    FASTEMBED_CACHE_PATH=/app/.modelcache \
    HF_HUB_DISABLE_SYMLINKS_WARNING=1
RUN python -c "from fastembed import TextEmbedding; \
    TextEmbedding('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2', \
    cache_dir='/app/.modelcache'); print('model gecachet')"

EXPOSE 3030

# EEN worker, meerdere threads. Elke worker houdt zijn eigen kopie van het
# embedmodel en van de vectormatrix in het geheugen; op deze VM is daar geen
# ruimte voor twee. Zoeken is kort werk, dus threads volstaan.
#
# Geen --preload: de opwarmthread moet in de worker draaien, niet in de master
# (die les kostte de vitrine veertien seconden 502 na elke herstart).
CMD ["gunicorn", "--bind", "0.0.0.0:3030", "--workers", "1", "--threads", "8", \
     "--timeout", "180", "demo:app"]
