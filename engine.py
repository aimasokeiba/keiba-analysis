import sqlite3
from pathlib import Path
import pandas as pd

DB = Path(__file__).parent / 'keiba.sqlite3'
ENTRY_COLUMNS = ['race_id','race_date','race_name','venue','surface','distance','horse_id','horse_name','horse_no','jockey']
HISTORY_COLUMNS = ['horse_id','race_date','venue','surface','distance','finish','field_size','margin']

def load_csv(file, required):
    df = pd.read_csv(file, dtype={'race_id':str,'horse_id':str}, encoding='utf-8-sig')
    missing = set(required)-set(df.columns)
    if missing:
        raise ValueError('不足している列: '+', '.join(sorted(missing)))
    df = df[required].copy()
    df['race_date'] = pd.to_datetime(df['race_date'], errors='coerce').dt.strftime('%Y-%m-%d')
    if df['race_date'].isna().any():
        raise ValueError('race_date は YYYY-MM-DD で入力してください')
    for c in ('distance','horse_no','finish','field_size','margin'):
        if c in df:
            df[c] = pd.to_numeric(df[c], errors='coerce')
    if 'horse_no' in df and (df['horse_no'].isna().any() or df['horse_no'].lt(1).any()):
        raise ValueError('horse_no は1以上の数値が必要です')
    if df[['horse_id']].isna().any().any():
        raise ValueError('horse_id が空です')
    return df

def store(entries, history):
    if entries.duplicated(['race_id','horse_id']).any():
        raise ValueError('出馬表に同じ race_id と horse_id の重複があります')
    with sqlite3.connect(DB) as conn:
        entries.to_sql('entries',conn,if_exists='replace',index=False)
        history.to_sql('history',conn,if_exists='replace',index=False)

def read_data():
    if not DB.exists():
        return None, None
    with sqlite3.connect(DB) as conn:
        return pd.read_sql('SELECT * FROM entries',conn),pd.read_sql('SELECT * FROM history',conn)

def score_race(entries, history):
    rows=[]
    for _, horse in entries.iterrows():
        past=history[(history.horse_id==horse.horse_id)&(history.race_date<horse.race_date)].copy()
        past=past.sort_values('race_date',ascending=False).head(5)
        valid=past[(past.finish>=1)&(past.field_size>=past.finish)&(past.field_size>1)]
        if valid.empty:
            rows.append({**horse.to_dict(),'score':None,'recent':None,'distance_fit':None,'surface_fit':None,'runs':0})
            continue
        # Position percentile: 100 for first, 0 for last; not a calibrated win probability.
        percentile=100*(valid.field_size-valid.finish)/(valid.field_size-1)
        weights=pd.Series([1/(i+1) for i in range(len(valid))],index=valid.index)
        recent=float((percentile*weights).sum()/weights.sum())
        same_surface=valid[valid.surface==horse.surface]
        surface_fit=float((100*(same_surface.field_size-same_surface.finish)/(same_surface.field_size-1)).mean()) if len(same_surface) else None
        near=valid[(valid.surface==horse.surface)&((valid.distance-horse.distance).abs()<=200)]
        distance_fit=float((100*(near.field_size-near.finish)/(near.field_size-1)).mean()) if len(near) else None
        # Neutral score for missing condition history, with a small uncertainty penalty.
        score=0.65*recent+0.20*(distance_fit if distance_fit is not None else 50)+0.15*(surface_fit if surface_fit is not None else 50)
        rows.append({**horse.to_dict(),'score':round(score,1),'recent':round(recent,1),'distance_fit':round(distance_fit,1) if distance_fit is not None else None,'surface_fit':round(surface_fit,1) if surface_fit is not None else None,'runs':len(valid)})
    return pd.DataFrame(rows).sort_values('score',ascending=False,na_position='last')
