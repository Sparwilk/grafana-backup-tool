#!/usr/bin/python
import json, requests, optparse, os, sys, datetime

def get_all_dashboards(grafana_url, headers):
    r = requests.get(grafana_url+"/api/search/", headers=headers)
    return json.loads(r.content)

def get_individual_dashboard(dashboard_uri, grafana_url, headers):
    r = requests.get(grafana_url + "/api/dashboards/" + dashboard_uri, headers=headers)
    return r.content

def create_index_if_missing(elasticsearch_url,index_name):
    index_url = elasticsearch_url + "/" + index_name
    r = requests.head(index_url)
    mappings = json.dumps({"settings": {"index.mapping.ignore_malformed": True }})

    if r.status_code == 404:
        r = requests.put(index_url, data=mappings)
        r = requests.head(index_url)
    if r.status_code == 200:
        return  index_url
    else:
        print r.text
        return ""

def save_dashboard_to_elasticsearch(dashboard_url, json_data):
    r = requests.put(dashboard_url, data=json_data)
    print json.dumps(r.json())
    return r.status_code

parser = optparse.OptionParser()

parser.add_option('-g', '--grafana-host',
    dest    = 'grafana_host',
    help    = 'The grafana host FQDN',
    metavar = 'GRAFANA_HOST')

parser.add_option('-P', '--grafana-port',
    default = '80',
    dest    = 'grafana_port',
    help    = 'The port grafana is running on',
    metavar = 'GRAFANA_PORT')

parser.add_option('-a', '--grafana-api-key',
    dest    = 'grafana_api_key',
    help    = 'The grafana API key (Viewer or higher)',
    metavar = 'GRAFANA_API_KEY')

parser.add_option('-e', '--elasticsearch-host',
    dest    = 'elastic_host',
    help    = 'The elasticsearch host FQDN',
    metavar = 'ELASTICSEARCH_HOST')

parser.add_option('-p', '--elasticsearch-port',
    default = '9200',
    dest    = 'elastic_port',
    help    = 'The port elasticsearch is running on',
    metavar = 'ELASTICSEARCH_PORT')

parser.add_option('-i', '--index-name',
    default = 'grafana-dash',
    dest    = 'index_name',
    help    = 'The name of the elasticsearch index to save the dashboards',
    metavar = 'ELASTICSEARCH_INDEX')

parser.add_option('-c', '--cron',
    default = False,
    dest    = 'run_as_cron',
    help    = 'Generate an automatic index name based on the default value + the current date',
    action  = 'store_true')

(options, args) = parser.parse_args()

if not options.elastic_host:
  parser.error('An elasticsearch host is required')
if not options.grafana_host:
  parser.error('An grafana host is required')

elastic_host = options.elastic_host
elastic_port = options.elastic_port
grafana_host = options.grafana_host
grafana_port = options.grafana_port
grafana_api_key = options.grafana_api_key
if options.run_as_cron:
    index_name = options.index_name + "-" + datetime.date.today().strftime('%Y.%m.%d')
else:
    index_name = options.index_name

http_get_headers = {'Authorization': 'Bearer ' + grafana_api_key}
http_post_headers = {'Authorization': 'Bearer ' + grafana_api_key, 'Content-Type': 'application/json'}

elasticsearch_url = "http://" + elastic_host + ":" + elastic_port 
grafana_url = "http://" + grafana_host + ":" + grafana_port

#Creates the index on ES if it doesn't already exist
index_url = create_index_if_missing(elasticsearch_url, index_name)

all_dashboards = get_all_dashboards(grafana_url, http_get_headers)

if not index_url:
    print "Unable to create index: " + index_url
    sys.exit(1)

for dashboard in all_dashboards:
    data = get_individual_dashboard(dashboard['uri'], grafana_url, http_get_headers)
    grafana_exported_dashboard = json.loads(data)
    grafana_exported_dashboard['dashboard']['id'] = None
    #Set the ID to none so that Grafana can assign it's own index when importing
    elasticsearch_format_dashboard = {
            "group": "guest",
            "tags": [],
            "user": "guest",
            "title": grafana_exported_dashboard['dashboard']['title'],
            "dashboard" : json.dumps(grafana_exported_dashboard['dashboard'])
            }
    #slug is URL compatible dashboard name
    elasticsearch_slug = grafana_exported_dashboard['meta']['slug']
    full_dashboard_url = index_url + "/dashboard/" + elasticsearch_slug
    save_dashboard_to_elasticsearch(full_dashboard_url, json.dumps(elasticsearch_format_dashboard))
sys.exit(0)
