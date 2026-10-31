import streamlit as st
import pandas as pd
from engine import ENTRY_COLUMNS,HISTORY_COLUMNS,load_csv,store,read_data,score_race

st.set_page_config(page_title='中央競馬 分析ダッシュボード',layout='wide')
st.title('中央競馬 分析ダッシュボード | CSV試作版')
st.caption('指数は過去の着順・頭数・条件一致度に基づく試作スコアであり、勝率や投資収益を示すものではありません。')
with st.expander('① CSVを取り込む',expanded=True):
    st.write('UTF-8（BOM付き可）のCSVを2種類選択してください。取り込み時は既存データを置き換えます。')
    a=st.file_uploader('出馬表 entries.csv',type='csv',key='a')
    b=st.file_uploader('過去走 history.csv',type='csv',key='b')
    if st.button('CSVを読み込んで保存',disabled=not(a and b)):
        try:
            e=load_csv(a,ENTRY_COLUMNS)
            h=load_csv(b,HISTORY_COLUMNS)
            store(e,h)
            st.success(f'保存しました：出馬表 {len(e)}行、過去走 {len(h)}行')
        except Exception as exc:
            st.error(str(exc))
entries,history=read_data()
if entries is None or entries.empty:
    st.info('まずCSVを取り込んでください。サンプルCSVは配布フォルダ内にあります。')
    st.stop()
entries['label']=entries.race_date+' | '+entries.venue+' | '+entries.race_name+' ('+entries.race_id+')'
choices=entries[['race_id','label']].drop_duplicates()
race_id=st.selectbox('② 分析するレース',choices.race_id.tolist(),format_func=lambda x: choices.loc[choices.race_id==x,'label'].iloc[0])
selected=entries[entries.race_id==race_id]
result=score_race(selected,history)
st.subheader('③ 出走馬の能力比較')
cols=['horse_no','horse_name','jockey','score','recent','distance_fit','surface_fit','runs']
st.dataframe(result[cols].rename(columns={'horse_no':'馬番','horse_name':'馬名','jockey':'騎手','score':'総合指数','recent':'近走指数','distance_fit':'距離適性','surface_fit':'芝・ダート適性','runs':'評価走数'}),hide_index=True,use_container_width=True)
chart=result.dropna(subset=['score']).set_index('horse_name')['score']
if not chart.empty:
    st.bar_chart(chart)
st.subheader('④ 馬別の過去走')
horse_id=st.selectbox('馬を選択',selected.horse_id.tolist(),format_func=lambda x:selected.loc[selected.horse_id==x,'horse_name'].iloc[0])
cutoff=selected.loc[selected.horse_id==horse_id,'race_date'].iloc[0]
past=history[(history.horse_id==horse_id)&(history.race_date<cutoff)].sort_values('race_date',ascending=False)
st.dataframe(past,hide_index=True,use_container_width=True)
st.caption('欠損条件は中立値50で代用。近走指数は直近最大5走の着順百分位を新しい走ほど重み付けした値です。未来のレース結果は分析に含めません。')
