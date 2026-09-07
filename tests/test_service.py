import copy, unittest
from service import CONFIGS, RequestError, validate_request

class ContractTests(unittest.TestCase):
    def setUp(self): self.body={'api_version':1,'id':'test','m':1,'n':1,'k':2,'a':[2,3],'b':[4,5]}
    def test_business_input(self): self.assertEqual(validate_request(self.body,CONFIGS['compact']),(1,1,2))
    def test_version(self):
        for version in [2,True,'1']:
            self.body['api_version']=version
            with self.assertRaises(RequestError): validate_request(self.body,CONFIGS['compact'])
    def test_bad_shapes_and_values(self):
        for key,value in [('m',0),('m',129),('m',True),('a',[2]),('a',[2,float('nan')]),('a',[2,1001]),('a',[2,10**1000]),('id','')]:
            b=copy.deepcopy(self.body); b[key]=value
            with self.assertRaises(RequestError): validate_request(b,CONFIGS['compact'])
    def test_no_extra_fields(self):
        self.body['shell']='untrusted'
        with self.assertRaises(RequestError): validate_request(self.body,CONFIGS['compact'])

if __name__=='__main__': unittest.main()
