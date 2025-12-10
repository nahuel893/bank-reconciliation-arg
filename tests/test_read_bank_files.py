import pandas as pd


df = pd.read_excel("./assets/banco/Ultimos_Movimientos.xls", header=7)

print("DATAFRAME BANK TEST")
print(df)

print("DATAFRAME SHAPE")
print(df.shape)
 
print("DATAFRAME COLUMNS")
print(df.columns)

print("DATAFRAME INFO")
print(df.info())

print("DATAFRAME MOUNT SUM")
print(f"${df['Importe'].sum():,.2f}")
print()
