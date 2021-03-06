import json
import scrapy

from http import HTTPStatus
from pydocumentdb import document_client


def get_or_create_database(client, db_name):
    try:
        return next(x for x in client.ReadDatabases()
                    if x['id'] == db_name)
    except StopIteration:
        return client.CreateDatabase({'id': self.db_name})


def get_or_create_collection(client, db, coll_name):
    try:
        return next(x for x in client.ReadCollections(db['_self'])
                    if x['id'] == coll_name)
    except StopIteration:
        return client.CreateCollection(db['_self'], {'id': coll_name})


class CosmosDBSaverPipeline(object):
    default_db_name = 'ted'
    default_coll_name = 'talks'

    def __init__(self, endpoint, key, db_name, coll_name):
        self.endpoint = endpoint
        self.key = key
        self.db_name = db_name
        self.coll_name = coll_name

    @classmethod
    def from_crawler(cls, crawler):
        return cls(
            endpoint=crawler.settings.get('COSMOSDB_ENDPOINT'),
            key=crawler.settings.get('COSMOSDB_KEY'),
            db_name=crawler.settings.get('COSMOSDB_DB_NAME',
                                         cls.default_db_name),
            coll_name=crawler.settings.get('COSMOSDB_COLLECTION_NAME',
                                           cls.default_coll_name)
        )

    def open_spider(self, spider):
        self.client = document_client.DocumentClient(self.endpoint,
                                                     {'masterKey': self.key})
        self.db = get_or_create_database(self.client, self.db_name)
        self.collection = get_or_create_collection(self.client, self.db,
                                                   self.coll_name)

    def process_item(self, item, spider):
        self.client.UpsertDocument(self.collection['_self'], item)
        return item


class TimingsDownloaderPipeline(object):
    timings_url = 'https://hls.ted.com/talks/{}.json'

    def __init__(self):
        pass

    @classmethod
    def from_crawler(cls, crawler):
        return cls()

    def process_item(self, item, spider):
        request = scrapy.Request(self.timings_url.format(item['id']))
        dfd = spider.crawler.engine.download(request, spider)
        dfd.addBoth(self.return_item, item)
        return dfd

    def return_item(self, response, item):
        if response.status != HTTPStatus.OK:
            return item
        timings = json.loads(response.text)
        item['timings'] = timings['timing']
        return item


class TranscriptDownloaderPipeline(object):
    transcript_url = 'https://www.ted.com/talks/{}/transcript.json'

    def __init__(self):
        pass

    @classmethod
    def from_crawler(cls, crawler):
        return cls()

    def process_item(self, item, spider):
        request = scrapy.Request(self.transcript_url.format(item['id']))
        dfd = spider.crawler.engine.download(request, spider)
        dfd.addBoth(self.return_item, item)
        return dfd

    def return_item(self, response, item):
        if response.status != HTTPStatus.OK:
            return item
        transcript = json.loads(response.text)
        item['transcript'] = [lines
                              for x in transcript['paragraphs']
                              for lines in x['cues']]
        return item
