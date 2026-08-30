# Publieke demo achter elevaitnv.com/demo.
#
# Het embedmodel zit in de image, zodat de container bij de start niets hoeft
# te downloaden en ook zonder internet werkt. Geen OCR-afhankelijkheden: de
# demo weigert scans met opzet.
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY kennisbank/ kennisbank/
COPY demo.py grenzen.py ./
COPY templates/ templates/

ENV EMBED_BACKEND=fastembed \
    FASTEMBED_CACHE_PATH=/app/.modelcache \
    HF_HUB_DISABLE_SYMLINKS_WARNING=1
RUN python -c "from fastembed import TextEmbedding; \
    TextEmbedding('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2', \
    cache_dir='/app/.modelcache'); print('model gecachet')"

EXPOSE 3030

# EEN worker, meerdere threads. Niet uit zuinigheid: de werkbank, de daglimiet
# per IP en de lijst met verwerkte documenten leven in het geheugen van het
# proces. Met twee workers zou "een verwerking tegelijk" er twee worden, "vijf
# per dag" tien, en zou een bezoeker kunnen landen op de worker die zijn
# document niet kent. De threads houden zoeken en lezen ondertussen snel; de
# werkbank serialiseert alleen het verwerken zelf.
#
# Geen --preload: de opwarmthread moet in de worker draaien, niet in de master
# (die les kostte de vitrine veertien seconden 502 na elke herstart).
CMD ["gunicorn", "--bind", "0.0.0.0:3030", "--workers", "1", "--threads", "8", \
     "--timeout", "180", "demo:app"]
