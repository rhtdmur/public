import json, boto3, os, re, base64

def lambda_handler(event, context):
    try:
        def getQuickSightDashboardUrl(awsAccountId, dashboardIdList, dashboardRegion):
            #Create QuickSight client
            quickSight = boto3.client('quicksight', region_name=dashboardRegion);
        
            #Construct dashboardArnList from dashboardIdList
            dashboardArnList=[ 'arn:aws:quicksight:'+dashboardRegion+':'+awsAccountId+':dashboard/'+dashboardId for dashboardId in dashboardIdList]
        
            #Generate Anonymous Embed url
            #Billing for anonymous embedding can be associated to a particular namespace. For our sample, we will pass in the default namespace.
            #ISVs who desire to track this at customer level can pass in the relevant customer namespace instead of default.
            response = quickSight.generate_embed_url_for_anonymous_user(
                     AwsAccountId = awsAccountId,
                     Namespace = 'default',
                     ExperienceConfiguration = {'Dashboard':{'InitialDashboardId':dashboardIdList[0]}},
                     AuthorizedResourceArns = dashboardArnList,
                     SessionLifetimeInMinutes = 60
                 )
            return response

        #Get AWS Account Id
        awsAccountId = context.invoked_function_arn.split(':')[4]
    
        #Read in the environment variables
        dashboardIdList = re.sub(' ','',os.environ['DashboardIdList']).split(',')
        dashboardNameList = os.environ['DashboardNameList'].split(',')
        dashboardRegion = os.environ['DashboardRegion']
    
        #You might want to embed QuickSight into static or dynamic pages.
        #We will use this API gateway and Lambda combination to simulate both scenarios.
        #In Dynamic mode, we will generate the embed url from QuickSight and send back an HTML page with that url specified.
        #In Static mode, we will first return static HTML. 
        #This page when loaded at client side will make another API gateway call to get the embed url and will then launch the dashboard.
        #We are handling these interactions by using a query string parameter with three possible values - dynamic, static & getUrl.
        mode='dynamic'
        response={} 
        if event['queryStringParameters'] is None:
            mode='dynamic'
        elif 'mode' in event['queryStringParameters'].keys():
            if event['queryStringParameters']['mode'] in ['static','getUrl']:
                mode=event['queryStringParameters']['mode']
            else:
                mode='unsupportedValue'
        else:
            mode='dynamic'
        
        #Set the html file to use based on mode. Generate embed url for dynamic and getUrl modes.
        #Also, If mode is static, get the api gateway url from event. 
        #In a truly static use case (like an html page getting served out of S3, S3+CloudFront),this url be hard coded in the html file
        #Deriving this from event and replacing in html file at run time to avoid having to come back to lambda 
        #to specify the api gateway url while you are building this sample in your environment.
        if mode == 'dynamic':
            htmlFile = open('content/DynamicSample.html', 'r')
            response = getQuickSightDashboardUrl(awsAccountId, dashboardIdList, dashboardRegion)
        elif mode == 'static':
            htmlFile = open('content/StaticSample.html', 'r')
            if event['headers'] is None or event['requestContext'] is None:
                apiGatewayUrl = 'ApiGatewayUrlIsNotDerivableWhileTestingFromApiGateway'
            else:
                apiGatewayUrl = event['headers']['Host']+event['requestContext']['path']
        elif mode == 'getUrl':
            response = getQuickSightDashboardUrl(awsAccountId, dashboardIdList, dashboardRegion)
    
        if mode in ['dynamic','static']:
            #Read contents of sample html file
            htmlContent = htmlFile.read()
        
            #Read logo file in base64 format
            logoFile = open('content/Logo.png','rb')
            logoContent = base64.b64encode(logoFile.read())
        
            #Replace place holders.
            htmlContent = re.sub('<DashboardIdList>', str(dashboardIdList), htmlContent)
            htmlContent = re.sub('<DashboardNameList>', str(dashboardNameList), htmlContent)
            #logoContent when cast to str is in format b'content'.
            #Array notation is used to extract just the content.
            htmlContent = re.sub('<LogoFileBase64>', str(logoContent)[2:-1], htmlContent)
            
            if mode == 'dynamic':
                #Replace Embed URL placeholder.
                htmlContent = re.sub('<QSEmbedUrl>', response['EmbedUrl'], htmlContent)
            elif mode == 'static':
                #Replace API Gateway url placeholder
                htmlContent = re.sub('<QSApiGatewayUrl>', apiGatewayUrl, htmlContent)
    
            #Return HTML. 
            return {'statusCode':200,
                'headers': {"Content-Type":"text/html"},
                'body':htmlContent
                }
        else:
            #Return response from generate embed url call.
            #Access-Control-Allow-Origin doesn't come into play in this sample as origin is the API Gateway url itself.
            #When using the static mode wherein initial static HTML is loaded from a different domain, this header becomes relevant.

            return {'statusCode':200,
                    'headers': {"Access-Control-Allow-Origin": "-",
                                "Content-Type":"text/plain"},
                    'body':json.dumps(response)
                    } 


    except Exception as e: #catch all
        return {'statusCode':400,
                'headers': {"Access-Control-Allow-Origin": "-",
                            "Content-Type":"text/plain"},
                'body':json.dumps('Error: ' + str(e))
                }     
