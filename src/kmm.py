import requests
import os
import sys
from version import *

packages = ['mlKode']

print("KodeScript Version {} > KMM Version {} → Installing {}...".format(version, kmmVersion, sys.argv[1]))
try:
    if os.path.isdir("./kode_modules") == True:
        if sys.argv[1] in packages:
            url = 'https://centeltech.com/kodescript/modules/{}/{}.txt'.format(sys.argv[1], sys.argv[1])
            txt = url[42:-1]+url[-1]
            myfile = requests.get(url)
            os.mkdir("./kode_modules/{}".format(txt[0:txt.find('/')]))
            open('./kode_modules/{}/{}.txt'.format(txt[0:txt.find('/')], txt[0:txt.find('/')]), 'wb').write(myfile.content)
            base = os.path.splitext('./kode_modules/{}/{}.txt'.format(txt[0:txt.find('/')], txt[0:txt.find('/')]))[0]
            os.rename('./kode_modules/{}/{}.txt'.format(txt[0:txt.find('/')], txt[0:txt.find('/')]), base + ".kode")
            print("Done!")
        else:
            print("Check Failed: No module named {}. Check your spelling and try again.".format(sys.argv[1]))
    else:
        if sys.argv[1] in packages:
            os.mkdir('./kode_modules')
            url = 'https://centeltech.com/kodescript/modules/{}/{}.txt'.format(sys.argv[1], sys.argv[1])
            txt = url[42:-1]+url[-1]
            myfile = requests.get(url)
            os.mkdir("./kode_modules/{}".format(txt[0:txt.find('/')]))
            open('./kode_modules/{}/{}.txt'.format(txt[0:txt.find('/')], txt[0:txt.find('/')]), 'wb').write(myfile.content)
            base = os.path.splitext('./kode_modules/{}/{}.txt'.format(txt[0:txt.find('/')], txt[0:txt.find('/')]))[0]
            os.rename('./kode_modules/{}/{}.txt'.format(txt[0:txt.find('/')], txt[0:txt.find('/')]), base + ".kode")
            print("Done!")
        else:
            print("Check Failed: No module named {}. Check your spelling and try again.".format(sys.argv[1]))
except FileExistsError:
  print("FileError → Cannot Create file/folder as it already exists. Try deleting the file/folder and try again!".format(version, kmmVersion))
# except:
#   print("Something else went wrong")
# myfile = requests.get(url)

# open('./kode_modules/', 'wb').write(myfile.content)