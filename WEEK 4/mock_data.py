import pandas as pd
import numpy as np
import os

# 1. 自动创建 docs 文件夹（如果不存在）
if not os.path.exists("docs"):
    os.makedirs("docs")

fake_brands = ["星辰百货", "云海超市", "极客数码", "味蕾餐厅", "潮流服饰", "幻境乐园", "金玉珠宝", "书香文苑"]
industries = ["零售", "餐饮", "数码", "服饰", "体验"]

data = []
for i in range(50):
    brand = np.random.choice(fake_brands) + str(i)
    revenue = np.random.randint(100000, 5000000)
    yoy = np.random.uniform(-0.3, 0.3)
    commission = revenue * np.random.uniform(0.05, 0.15)
    commission_yoy = np.random.uniform(-0.2, 0.2)

    data.append({
        "品牌": brand,
        "营业额": revenue,
        "营业额同比": yoy,
        "抽成": commission,
        "抽成同比": commission_yoy,
        "业态": np.random.choice(industries)
    })

df = pd.DataFrame(data)

# 保存
df.to_excel("docs/brands_mock.xlsx", index=False)
print("✅ 假数据生成完毕！保存在 WEEK 4/docs/brands_mock.xlsx")
