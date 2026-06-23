import urllib3
import warnings
from requests.exceptions import RequestsDependencyWarning

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings("ignore", category=RequestsDependencyWarning)