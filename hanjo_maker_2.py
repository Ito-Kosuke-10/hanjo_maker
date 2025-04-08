import streamlit as st
import pandas as pd
import folium
import requests
from streamlit_folium import st_folium
from math import pi
import os

# ✅ ローカルなら.envを読み込む（クラウドでは無視される）
try:
    from dotenv import load_dotenv
    load_dotenv()
except:
    pass

# ✅ APIキーの取得（ローカル優先→クラウドSecrets fallback）
API_KEY = os.getenv("API_KEY")
if not API_KEY:
    API_KEY = st.secrets["API_KEY"]  # ←ここ重要！

st.set_page_config(layout="wide")
st.title("📍 Hanjo Maker - 商圏分析アプリ")

# 入力欄とスライダー
address = st.text_input("出店候補の住所を入力してください", "渋谷駅")
radius = st.slider("表示する半径（メートル）", 100, 1000, step=100, value=500)

if address and API_KEY:
    # Geocoding APIで緯度経度を取得
    geo_url = f"https://maps.googleapis.com/maps/api/geocode/json?address={address}&key={API_KEY}&language=ja"
    geo_res = requests.get(geo_url).json()

    if geo_res["status"] == "OK":
        lat = geo_res["results"][0]["geometry"]["location"]["lat"]
        lon = geo_res["results"][0]["geometry"]["location"]["lng"]
        st.success(f"住所: {address} → 緯度: {lat:.4f}, 経度: {lon:.4f}")

        # Places APIで飲食店を取得
        places_url = (
            f"https://maps.googleapis.com/maps/api/place/nearbysearch/json"
            f"?location={lat},{lon}&radius={radius}&type=restaurant&key={API_KEY}&language=ja"
        )
        places_res = requests.get(places_url).json()

        restaurant_data = []
        for result in places_res.get("results", []):
            types = result.get("types", [])
            genre = ", ".join(types) if types else "不明"

            restaurant_data.append({
                "name": result.get("name", "名称不明"),
                "lat": result["geometry"]["location"]["lat"],
                "lon": result["geometry"]["location"]["lng"],
                "genre": genre,
                "rating": result.get("rating", 0),
                "reviews": result.get("user_ratings_total", 0),
                "address": result.get("vicinity", "住所不明")
            })

        df = pd.DataFrame(restaurant_data)
        if "genre" not in df.columns:
            df["genre"] = "不明"

        # 地図表示
        m = folium.Map(location=[lat, lon], zoom_start=16)
        folium.Circle([lat, lon], radius=radius, color="red", fill=True, fill_opacity=0.1).add_to(m)
        folium.Marker([lat, lon], tooltip="出店候補地", icon=folium.Icon(color="red")).add_to(m)

        for _, row in df.iterrows():
            folium.Marker(
                [row["lat"], row["lon"]],
                tooltip=f"{row['name']}（{row['rating']}★ / {row['reviews']}件）",
                popup=row["address"],
                icon=folium.Icon(color="blue", icon="cutlery", prefix='fa')
            ).add_to(m)

        st.subheader("📍 周辺飲食店マップ")
        st_folium(m, width=800, height=500)

        # 商圏分析
        st.subheader("📊 商圏データ分析")
        area_m2 = pi * (radius ** 2)
        density = len(df) / (area_m2 / 1e6)

        col1, col2 = st.columns(2)
        col1.metric("飲食店数", f"{len(df)} 店舗")
        col2.metric("密度（/km²）", f"{density:.1f} 店舗/km²")

        # ジャンル分析
        all_genres = []
        for g in df["genre"]:
            all_genres.extend(g.split(", "))
        genre_series = pd.Series(all_genres).value_counts()

        st.write("ジャンル別 店舗数ランキング（多い順）")
        st.dataframe(genre_series.head(5).rename_axis("ジャンル").reset_index(name="店舗数"))

        st.write("ジャンル別 店舗数（少ない順）")
        st.dataframe(genre_series.tail(5).rename_axis("ジャンル").reset_index(name="店舗数"))

        # 人気店ランキング
        selected_genre = st.selectbox("ジャンルを選択して人気店を確認", ["すべて"] + list(genre_series.index))
        if selected_genre != "すべて":
            filtered = df[df["genre"].str.contains(selected_genre)]
            top_rated = filtered.sort_values(by="rating", ascending=False)[["name", "rating", "reviews"]]
            st.write(f"{selected_genre} の人気店ランキング")
            st.dataframe(top_rated.head(5))

        st.subheader("🧠 出店スコア（ダミー）")
        st.metric("商圏スコア", "A（88点）")
        st.metric("競合スコア", "B（65点）")
        st.info("※ 今後は人口、家賃、流動人口などを使ってスコアを自動化予定。")

    else:
        st.warning("住所が見つかりませんでした。入力内容を確認してください。")

elif not API_KEY:
    st.error("⚠️ APIキーが見つかりませんでした。`.env` または Streamlit Secrets に設定してください。")
