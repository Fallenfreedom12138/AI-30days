import pandas as pd #读文档工具 pandas
from pathlib import Path #读文档工具 Path


from pathlib import Path
import pandas as pd

def load_documents(folder_path):
    documents=[]

    for file in Path(folder_path).glob("*.xlsx"):
        df=pd.read_excel(file)

        for _,row in df.iterrows():
            parts=[]
            for col in df.columns:
                value=row[col]
                if col in ["营业额同比"]:
                value=f"{value*100:.1f}%"
                parts.append(f"{col}:{value}")
            text=", ".join(parts)
            documents.append({
                "content":text,
                "sou  rce": file.name
            })
    return documents