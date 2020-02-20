#!/usr/bin/env python3

import os
from dotenv import load_dotenv
import requests
from urllib.parse import urlparse
import re
import json
import base64
from bs4 import BeautifulSoup
import socket
import time
from datetime import datetime

load_dotenv()
os.system('clear')

DEBUG = True
RUN_INTERVAL = 60 * 500
EAGLE_LOGIN = os.getenv('EAGLE_LOGIN')
EAGLE_PASS = os.getenv('EAGLE_PASS')
SITE_LOGIN = os.getenv('SITE_LOGIN')
SITE_PASS = os.getenv('SITE_PASS')
SITE_DOMAIN = 'http://savoy' if bool( re.match('^.*local.*$', socket.gethostname()) ) else 'https://savoy.com.au'
WP_REST_TOKEN = base64.standard_b64encode( bytes(SITE_LOGIN + ':' + SITE_PASS, encoding='utf-8') )
HEADERS_AUTH_WP = {'Authorization': 'Basic ' + WP_REST_TOKEN.decode('utf-8'), 'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/74.0.3729.131 Safari/537.36'}
HEADERS_EAGLE_TOKEN_REQUEST = {'Content-Type': 'application/vnd.api+json'}
EAGLE_TOKEN_BODY = {
	'data': {
		'type': 'sessions',
		'attributes': {
			'email': EAGLE_LOGIN,
			'password': EAGLE_PASS
		}
	}
}


def log(text, color = ''):
	colors = {
		'black': '\x1b[30m',
		'red': '\x1b[31m',
		'green': '\x1b[32m',
		'yellow': '\x1b[33m',
		'blue': '\x1b[34m',
		'magenta': '\x1b[35m',
		'cyan': '\x1b[36m',
		'white': '\x1b[37m'
	}
	print(colors.get(color, '\x1b[0m'), text, '\x1b[0m')


def debug(text):
	if not DEBUG:
		return

	print(text)


def getEagleToken():
	try:
		tokenResponse = requests.post('https://www.eagleagent.com.au/api/v2/sessions', data=json.dumps(EAGLE_TOKEN_BODY), headers=HEADERS_EAGLE_TOKEN_REQUEST)
		try:
			response = json.loads(tokenResponse.text)

			if 'errors' in response:
				log('Authentication failed. %s' % response['errors'][0]['detail'], 'red')
				exit(-1)

			if 'data' in response:
				return response['data']['attributes']['token']

		except Exception as e:
			log('Error while trying to parse JSON. %s' % e, 'red')
			exit(-1)

	except Exception as e:
		log(e, 'red')
		exit(-1)


def req(method, url, dataType='json', data='', headers={}):
	try:
		response = requests.request(method, url, data=data, headers=headers)

		try:
			if dataType == 'json':
				data = json.loads(response.text)
			elif dataType == 'binary':
				data = response.content

			return data

		except Exception as e:
			log('Couldn\'t parse Response. %s' %e, 'red')
			exit(-1)

	except requests.exceptions.RequestException as e:
		log(str(e.response) + ' %s' % url, 'red')
		exit(-1)


def convertDate(dateStr):
	# convert 2020-02-01T12:30:00.000+11:00
	# to      2020-02-01T12:30:00.000+1100
	s = dateStr[::-1].replace(':', '', 1)[::-1]

	# 2020/02/01 12:30
	return datetime.strptime(s, '%Y-%m-%dT%H:%M:%S.%f%z').strftime('%Y/%m/%d %H:%M')

 
def getSitePropertiesList():
	page = 1
	limit = 100
	output = []

	while True:
		propsData = {
			'per_page': limit,
			'page': page
		}
		response = reqToWPREST('GET', SITE_DOMAIN + '/wp-json/wp/v2/property', data=json.dumps(propsData))

		for item in response:
			output.append(item)

		if len(response) < limit:
			return output

		page += 1


def getCRMPropertiesList():
	offset = 0
	limit = 60
	output = []

	try:
		while True:
			response = requests.get('https://www.eagleagent.com.au/api/v2/properties?page%5Blimit%5D=' + str(limit) + '&page%5Boffset%5D=' + str(offset), headers=HEADERS_AUTH_EAGLE)
			log('request...')

			try:
				data = json.loads(response.text)

				for item in data['data']:
					output.append(item)

				if len(data['data']) < limit:
					debug('Received all data from CRM.')
					return output

			except Exception as e:
				log('Error while trying to parse JSON. %s' % e, 'red')
				exit(-1)
			
			offset += 60

	except Exception as e:
		log('Error while trying to get properties. %s' % e, 'red')
		exit(-1)


# temp save it as a file
# with open('crm.json', 'w') as file:
	# file.write( json.dumps(getCRMPropertiesList()) )

# temp save it as a file
# for item in t:
	# log('%s	%s %s' % (item['id'], item['attributes']['property_type'], item['attributes']['full_address']), 'yellow')


def reqToWPREST(method, url, data='', headers={}, files={}):
	if not headers:
		headers=HEADERS_AUTH_WP

	try:
		req = requests.request(method, url, data=data, headers=headers, timeout=10)
		responseCode = req.status_code
		response = req.text
	except Exception as e:
		log('Exception in request. ' + str(e) + ' %s' % url, 'red')
		responseCode = False
	
	if responseCode:
		try:
			result = json.loads(response)

			return result

		except Exception as e:
			log('%s. %s. %s. %s' % (url, responseCode, data, response), 'red')
			exit(-1)

	else:
		# Try again
		return reqToWPREST(method, url, data, headers)


def reqToWPRESTAttachment(url):
	image = req('GET', url, dataType='binary')

	imageName = os.path.basename( urlparse(url).path )
	imageExtention = os.path.splitext(url)[1][1:]
	headers = {'Authorization': 'Basic ' + WP_REST_TOKEN.decode('utf-8'), 'Content-Type': 'image/%s' % imageExtention, 'Content-Disposition': 'attachment; filename=%s' % imageName, 'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/74.0.3729.131 Safari/537.36'}
	response = reqToWPREST('POST', SITE_DOMAIN +  '/wp-json/wp/v2/media', data=image, headers=headers)

	if 'id' in response:
		return response['id']

	return ''



def normalizeTitle(string):
	return string.replace(' ', '').replace(',', '').lower()


def normalizePostContent(htmlStr):
	text = BeautifulSoup(htmlStr, 'html.parser').text

	# remove all special chars
	text = re.sub('[^A-Za-z0-9]+', '', text)
	
	return text


def normalizePropertyDesc(text):
	if text is None:
		return ''

	# remove all special chars
	text = re.sub('[^A-Za-z0-9]+', '', text)

	return text


def checkProperties():
	# Sale statuses: active, under offer, sold
	# Rent statuses: active, let, under application

	site = getSitePropertiesList()
	crm = getCRMPropertiesList()

	log('got %d entries from Eagle' % len(crm), 'yellow')
	log('got %d entries from WordPress' % len(site), 'yellow')
	start = time.perf_counter()

	# G09/1 Queen Street, Blackburn, VIC, 3130				 # site
	# G09 / 1 Queen Street, Blackburn						 # crm

	i = 0
	obj = {}
	for k, citem in enumerate(crm):
		for j, sitem in enumerate(site):
			stitle = normalizeTitle(sitem['title']['rendered'])
			ctitle = normalizeTitle(citem['attributes']['full_address'])
			ctitlefull = normalizeTitle('%s %s %s' % (citem['attributes']['full_address'], citem['attributes']['state'], citem['attributes']['postcode']))
			sdesc = normalizePostContent( sitem['content']['rendered'] )
			cdesc = normalizePropertyDesc( citem['attributes']['description'] )

			if stitle == ctitlefull or stitle == ctitle:

				if len(sdesc) < len(cdesc):
					min = sdesc
					max = cdesc
				else:
					min = cdesc
					max = sdesc
				pattern = re.compile('^.*' + min + '.*$', re.DOTALL)

				if bool( re.match(pattern, max) ):
					if sitem['id'] in d:
						del obj[sitem['id']]
					i += 1
					break
				else:
					obj.update( {sitem['id']: sitem} )
				
			else:
				pass

	log(i, 'magenta')
	log(time.perf_counter() - start, 'white')
	log(json.dumps(obj))


def submitProperty(property, post=None, update=False):

	if update:
		# remove terms
		reqToWPREST('DELETE', SITE_DOMAIN + '/wp-json/wp/v2/property-terms/%d' % post['id'])

	prop = property['attributes']

	# media: featured
	if update:
		if prop['primary_image']:
			if not post['_thumbnail_id']:
				# if featured images was added later
				featuredID = reqToWPRESTAttachment(prop['primary_image'])
			else:
				# check if it was chnaged
				if prop['primary_image'] != post['_thumbnail_name']:
					# changed
					featuredID = reqToWPRESTAttachment(prop['primary_image'])
				else:
					# the same
					featuredID = post['_thumbnail_id']
		else:
			# unset featured image
			featuredID = ''
	else:
		# set initially
		if prop['primary_image']:
			debug('Trying to upload featured attachment.')
			featuredID = reqToWPRESTAttachment(prop['primary_image'])
			if featuredID:
				debug('Featured attachment uploaded. %s' % featuredID)
		else:
			featuredID = ''


	# media: property images
	if property['relationships']['images']['links']['related']:
		propertyImagesResponse = req('GET', property['relationships']['images']['links']['related'], headers=HEADERS_AUTH_EAGLE)
	if not 'errors' in propertyImagesResponse:
		if update:
			if 'data' in propertyImagesResponse:
				crmImageIDs = []
				siteImageIDs = []
				for id in post['crm_image_ids']:
					for i, image in enumerate(propertyImagesResponse['data']):
						if image['id'] == id:
							siteImageIDs.append(id)							
							crmImageIDs.append(image['id'])
							break
						else:
							if i == len(propertyImagesResponse) - 1:
								debug('Posting new attachment...')
								imageID = reqToWPRESTAttachment(image['attributes']['url'])
								if imageID:
									siteImageIDs.append(imageID)
									debug('Attachment id=%s submitted.' % imageID)
								crmImageIDs.append(image['id'])
			else:
				debug('No data received from %s' % property['relationships']['images']['links']['related'])
				# unset
				crmImageIDs = []
				siteImageIDs = []

		else:
			# set initially
			crmImageIDs = []
			siteImageIDs = []
			if 'data' in propertyImagesResponse:
				for image in propertyImagesResponse['data']:
					debug('Posting new attachment initially...')
					imageID = reqToWPRESTAttachment(image['attributes']['url'])
					if imageID:
						siteImageIDs.append(imageID)
						debug('Attachment id=%s submitted.' % imageID)
					crmImageIDs.append(image['id'])
	else:
		crmImageIDs = []
		siteImageIDs = []
		log('Error while trying to get Eagle images response. %s.' % propertyImagesResponse['errors'][0]['detail'], 'red')

	# OFI
	dateOFI = ''
	ofiResponse = req('GET', property['relationships']['inspections']['links']['related'], headers=HEADERS_AUTH_EAGLE)
	if 'data' in ofiResponse and len(ofiResponse['data']):
		# get actual(last) OFI
		start = ofiResponse['data'][len(ofiResponse['data']) - 1]['attributes']['start_datetime']
		end = ofiResponse['data'][len(ofiResponse['data']) - 1]['attributes']['end_datetime']

		dateOFI = {
			'property_ofi': {
				'from': convertDate(start),
				'to': convertDate(end)
			}
		}

	# content
	title = '%s, %s, %s' % (prop['full_address'], prop['state'], prop['postcode'])
	content = '<strong>' + prop['headline'] + '</strong>\n' + prop['description']

	# floor plans
	floorPlansResponse = req('GET', property['relationships']['floorplans']['links']['related'])
	if 'data' in floorPlansResponse and len(floorPlansResponse['data']):
		# get 1st one. In db it might have multiple, but Front-End doen't support multiple images
		floorPlan = {'fave_plan_title': 'Floor plan', 'fave_plan_image': floorPlansResponse['data'][0]['attributes']['url']}
		floorPlanShow = 'enable'
	else:
		floorPlan = ''
		floorPlanShow = 'disable'

	# status
	propStatus = prop['status'].lower()
	if propStatus == 'active':
		if prop['sale_or_rent'].lower() == 'rent':
			if dateOFI:
				status = ['for rent', 'rental OFI']
			else:
				status = ['for rent']
		elif prop['sale_or_rent'].lower() == 'sale':
			if dateOFI:
				status = ['for sale', 'sales OFI']
			else:
				status = ['for sale']
	elif propStatus == 'under offer':
		status = ['for sale', 'under offer']
	elif propStatus == 'under application':
		status = ['for rent', 'under application']
	elif propStatus == 'let':
		status = ['leased']
	else:
		# Sold
		status = [status]

	# features
	featuresList = [prop['indoor_features'], prop['heating_cooling_features'], prop['eco_friendly_features'], prop['outdoor_features'], prop['other_features']]
	features = []
	for feature in featuresList:
		feature = feature.replace(',', '|')
		feature = feature.split('|')
		if isinstance(feature, list):
			for feature2 in feature:
				if feature2:
					features.append(feature2.strip())
		else:
			features.append(feature.strip())

	# states
	states = {
		'VIC': 'Victoria',
		'ACT': 'Australian Capital Territory',
		'NSW': 'New South Wales',
		'NT': 'Northern Territory',
		'WA': 'Western Australia'
	}

	# agents
	agents = {
		'816': 6378,
		'10326': 6994,
		'3603': 2948,
		'4911': 3393,
		'10228': 7061,
		'2345': 158,
		'3130': 72,
		'2415': 150,
		#???: 156,
		#???: 2048,
		'2398': 2018
	}
	# get last id in agents array
	agent = agents[prop['agent_ids'][len(prop['agent_ids']) - 1]]

	# price
	price = prop['alt_to_price'] if prop['alt_to_price'] else prop['price'] if prop['price'] and prop['price'] != '0.0' else prop['advertised_price']

	# map
	mapShow = 1 if prop['latitude'] else 0
	mapCoords = '%s,%s' % (prop['latitude'], prop['longitude']) if prop['latitude'] else ''

	data ={
		'crm_id': property['id'],
		'crm_updated': prop['updated_at'],
		# content
		'title': title,
		'content': content,
		'_thumbnail_id': featuredID,
		'_thumbnail_name': prop['primary_image'],
		'status': 'publish',
		'author': 12, # automation
		# terms
		'property_type': prop['property_type'],
		'property_feature': features,
		'property_status': status,
		'property_city': prop['suburb'],
		'property_area': prop['municipality'],
		'property_state': states[prop['state']],
		# meta
		'fave_property_price': price,
		'fave_property_land': prop['land_size'],
		'fave_property_size_prefix': prop['house_size_units'],
		'fave_property_land_postfix': prop['land_size_units'],
		'fave_property_bedrooms': prop['bedrooms'],
		'fave_property_bathrooms': prop['bathrooms'],
		'fave_property_garage': prop['garage_spaces'],
		'fave_property_map': mapShow, # 1/0. default: 0
		'houzez_geolocation_lat': prop['latitude'],
		'houzez_geolocation_long': prop['longitude'],
		'fave_property_map_address': prop['full_address'],
		'fave_property_location': mapCoords,
		'fave_property_address': prop['formatted_address_line_1'],
		'fave_property_zip': prop['postcode'],
		'fave_property_country': 'AU',
		'fave_agent_display_option': 'agent_info',
		'fave_agents': agent,
		'fave_floor_plans_enable': floorPlanShow, # enable/disable. default: disable
		'floor_plans': floorPlan,
		'fave_video_url': prop['video_url'],
		'crm_image_ids': crmImageIDs,
		'fave_property_images': siteImageIDs,
		'fw_options': dateOFI
		# some defaults
		# 'fave_featured': 0,
		# 'fave_property_size': '',
		# 'fave_property_year': '',
		# 'fave_property_garage_size': '',
		# 'fave_property_map_street_view': 'hide,
		# 'fave_prop_homeslider': 'no',
		# 'fave_multiunit_plans_enable': 'disable',
		# 'fave_multi_units': [],
		# 'fave_single_top_area': 'global',
		# 'fave_single_content_area': 'global',
		# 'fave_additional_features_enable':  'disable',
		# 'additional_features': [],
	}
	debug(json.dumps(data))

	if update:
		debug('Property exists, so update it.')
		response = reqToWPREST('POST', SITE_DOMAIN + '/wp-json/wp/v2/property/%s' % post['id'], data=json.dumps(data))
	else:
		debug('Add a new property.')
		response = reqToWPREST('POST', SITE_DOMAIN + '/wp-json/wp/v2/property', data=json.dumps(data))

	if 'id' in response:
		log('Property id=%s was %s. URL=%s' % (response['id'], 'updated' if update else 'added', response['link']), 'yellow')

		# attach attachments to post
		dataAttach = {
			'post_parent': response['id']
		}
		attachList = siteImageIDs + [featuredID] if featuredID else siteImageIDs
		for attachID in attachList:
			reqToWPREST('POST', SITE_DOMAIN + '/wp-json/wp/v2/media/%s' % attachID, data=json.dumps(dataAttach))

	else:
		log('Property wasn\'t %s. %s' % ('updated' if update else 'added', response), 'red')
		exit(-1)


def getPostByCRMID(crmID, posts):
	for post in posts:
		if post['crm_id'] == crmID:
			return post


def checkPropertyChanges(post, property):
	prop = property['attributes']
	propStatus = prop['status'].lower()

	if prop['updated_at'] == post['crm_updated']:
		# runaway if not changed
		return

	if propStatus in ['active', 'let', 'under application', 'under offer', 'sold']:
		# update property post
		submitProperty(property, post, True)

	else:
		# remove property post
		rdata = {
			'force': False
		}
		req = reqToWPREST('DELETE', SITE_DOMAIN + '/wp-json/wp/v2/property/%d' % post['id'], data=json.dumps(rdata))
		if req['deleted']:
			log('Property id=%s was deleted. Status %s -> %s' % (post['id'], post['property_status'], prop['status']), 'cyan')
		else:
			log('Property wasn\'t deleted. %s. Status %s -> %s' % (req, post['property_status'], prop['status']), 'red')



def checkNewProperties():
	try:
		with open('crm.json', 'r') as file:
			dataFromCRMOld = json.loads(file.read())
	except OSError as e:
		log('Cannot open the file %s. %s' % ('crm.json', e), 'red')
		exit(-1)

	dataFromCRM = getCRMPropertiesList()
	dataFromSite = getSitePropertiesList()

	for item in dataFromCRM:
		for i, item2 in enumerate(dataFromCRMOld):
			# work only with difference in items. ignore old entries.
			if item['id'] != item2['id']:
				if len(dataFromCRMOld) - 1 == i:

					status = item['attributes']['status'].lower()

					post = getPostByCRMID(item['id'], dataFromSite)

					if post and 'crm_id' in post and len(post['crm_id']) > 0:
						checkPropertyChanges(post, item)
					else:
						if status in ['active', 'let', 'under application', 'under offer', 'sold']:
							pass
						else:
							# do not pass others
							continue

						submitProperty(item)

			else:
				break


def run():
	print('Start...')
	checkNewProperties()


if __name__ == '__main__':
	while True:
		eagleToken = getEagleToken()
		HEADERS_AUTH_EAGLE = {'Authorization': eagleToken, 'Content-Type': 'application/vnd.api+json'}
		run()
		time.sleep(RUN_INTERVAL)
