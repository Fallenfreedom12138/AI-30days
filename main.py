# This is a sample Python script.

# Press Shift+F10 to execute it or replace it with your code.
# Press Double Shift to search everywhere for classes, files, tool windows, actions, and settings.
import json


def print_hi(name):
    # Use a breakpoint in the code line below to debug your script.
    print(f'Hi, {name}')  # Press Ctrl+F8 to toggle the breakpoint.


# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    print_hi('PyCharm')

# See PyCharm help at https://www.jetbrains.com/help/pycharm/
import json
project={'品牌名':'salomon','楼层':'2','业态':'运动','本月营业额':150}
json_str=json.dumps(project,ensure_ascii=False, indent=2)
print(json_str)

dict=json.loads(json_str)
print(dict['品牌名'])

project1={'品牌名':'FILA','楼层':'3','业态':'运动','本月营业额':130}
project2={'品牌名':'UA','楼层':'1','业态':'运动','本月营业额':140}
list1=[project,project1,project2]
list1_json=json.dumps(list1,ensure_ascii=False, indent=2)
print(list1_json)
with open("brands.json","w",encoding="utf-8")as f:
    json.dump(list1,f,ensure_ascii=False, indent=2)

with open("brands.json","r",encoding="utf-8")as f:
    brands=json.load(f)
for b in brands:
    print(b)


with open(".env","w",encoding="utf-8")as f:
    f.write("API_KEY=test_key_12345\n")


import os
from dotenv import load_dotenv
load_dotenv()
api_key=os.getenv("API_KEY")
print(api_key)