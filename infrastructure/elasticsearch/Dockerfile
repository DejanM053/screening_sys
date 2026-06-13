FROM elasticsearch:8.13.0

# Required for the phonetic (double_metaphone) analyzer used by
# infrastructure/elasticsearch/mappings.json
RUN bin/elasticsearch-plugin install --batch analysis-phonetic
