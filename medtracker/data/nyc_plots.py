import pandas as pd
import plotly.graph_objects as go
import numpy as np

def prepFigure(figure, title):
    figure.update_xaxes(tickformat='%a<br>%b %d',
        tick0 = '2020-03-22',
        dtick = 7 * 24 * 3600000,
        rangeselector=dict(
            buttons=list([
                dict(count=7, label="1w", step="day", stepmode="backward"),
                dict(count=14, label="2w", step="day", stepmode="backward"),
                dict(count=1, label="1m", step="month", stepmode="backward"),
                dict(count=1, label="YTD", step="year", stepmode="todate"),
                dict(step="all")
            ])
        )
    )
    figure.update_layout(title="<b>" + title + "</b>", hovermode="x",  
                         legend_orientation="h",
                         margin={"r":10,"l":30})
    return figure

start_date = "2020-03-01"

#confirmed cases
url = "https://usafactsstatic.blob.core.windows.net/public/data/covid-19/covid_confirmed_usafacts.csv"
confirmed_df=pd.read_csv(url)

nyc_counties_df = confirmed_df.loc[(confirmed_df['State'] == 'NY') & (confirmed_df['countyFIPS'].isin([36005, 36061, 36081, 36085, 36047]))]
nyc_counties_df=nyc_counties_df.set_index('County Name')
nyc_counties_df=nyc_counties_df.drop(columns=['countyFIPS', 'State', 'stateFIPS'])
nyc_counties_df = nyc_counties_df.transpose()
nyc_counties_df = nyc_counties_df.rename_axis('Date')
nyc_counties_df.index =pd.to_datetime(nyc_counties_df.index)
nyc_counties_df['Total'] = nyc_counties_df['Bronx County'] + nyc_counties_df['Kings County'] + nyc_counties_df['New York County'] + nyc_counties_df['Queens County'] + nyc_counties_df['Richmond County']


#confirmed deaths
url = "https://usafactsstatic.blob.core.windows.net/public/data/covid-19/covid_deaths_usafacts.csv"
deaths_df = pd.read_csv(url)

nyc_counties_deaths_df = deaths_df.loc[(deaths_df['State'] == 'NY') & (deaths_df['countyFIPS'].isin([36005, 36061, 36081, 36085, 36047]))]

nyc_counties_deaths_df=nyc_counties_deaths_df.set_index('County Name')
nyc_counties_deaths_df=nyc_counties_deaths_df.drop(columns=['countyFIPS', 'State', 'stateFIPS'])

nyc_counties_deaths_df = nyc_counties_deaths_df.transpose()
nyc_counties_deaths_df = nyc_counties_deaths_df.rename_axis('Date')
nyc_counties_deaths_df.index =  pd.to_datetime(nyc_counties_deaths_df.index)

nyc_counties_deaths_df['Total'] = nyc_counties_deaths_df['Bronx County'] + nyc_counties_deaths_df['Kings County'] + nyc_counties_deaths_df['New York County'] + nyc_counties_deaths_df['Queens County'] + nyc_counties_deaths_df['Richmond County']

#case fatality ratio
cfr_df = nyc_counties_deaths_df / nyc_counties_df 

#daily cases
def dailydata(dfcounty):
    dfcountydaily=dfcounty.diff(axis=0)#.fillna(0)
    return dfcountydaily

DailyCases_df=dailydata(nyc_counties_df)
DailyDeaths_df=dailydata(nyc_counties_deaths_df)
DailyCases_df = DailyCases_df.loc[start_date:]
# compute 7-day exponential moving average
DailyCases_df['EMA'] = DailyCases_df['Total'].ewm(span=7).mean()

#daily deaths
DailyDeaths_df = DailyDeaths_df.loc[start_date:]
DailyDeaths_df.replace(0.0,np.nan, inplace=True)
# compute 7-day exponential moving average
DailyDeaths_df['EMA'] = DailyDeaths_df['Total'].ewm(span=7).mean()
DailyDeaths_df = DailyDeaths_df.loc[start_date:]
DailyDeaths_df.replace(0.0,np.nan, inplace=True)
# compute 7-day exponential moving average
DailyDeaths_df['EMA'] = DailyDeaths_df['Total'].ewm(span=7).mean()

#NYC case hospitalizations
url = "https://raw.githubusercontent.com/nychealth/coronavirus-data/master/trends/data-by-day.csv"

nyc_case_hosp_death_df = pd.read_csv(url)
nyc_case_hosp_death_df.index =pd.to_datetime(nyc_case_hosp_death_df.iloc[:,0])
nyc_case_hosp_death_df = nyc_case_hosp_death_df.drop(nyc_case_hosp_death_df.columns[0], axis=1)
nyc_case_hosp_death_df = nyc_case_hosp_death_df.rename_axis('Date')

#r0 estimation
url = "https://d14wlfuexuxgcm.cloudfront.net/covid/rt.csv"
rt_df = pd.read_csv(url)
rt_df = rt_df.rename(columns={"mean":"R0_mean"})

#### PLOTS ####
# case fatality ratio
df2 = cfr_df.loc["2020-03-14":,]
fig2 = go.Figure()
fig2.add_scatter(x=df2.index, y=df2['Bronx County'], mode='lines', name='Bronx')
fig2.add_scatter(x=df2.index, y=df2['Kings County'], mode='lines',name='Brooklyn')
fig2.add_scatter(x=df2.index, y=df2['Queens County'], mode='lines', name='Queens')
fig2.add_scatter(x=df2.index, y=df2['New York County'], mode='lines', name='Manhattan')
fig2.add_scatter(x=df2.index, y=df2['Richmond County'], mode='lines', name='Staten Island')
fig2.add_scatter(x=df2.index, y=df2['Total'], mode='lines+markers', name='NYC')
prepFigure(fig2, title='NYC Case Fatality Rate - From USA Facts')
fig2.update_layout(yaxis_title="Percent", yaxis_tickformat=".2%")
fig2.write_json("/home/ubuntu/medtracker/medtracker/data/cfr.json")

#daily new cases
df2 = DailyCases_df
fig2 = go.Figure()
fig2.add_scatter(x=df2.index,y=df2['Bronx County'], mode='lines', name='Bronx')
fig2.add_scatter(x=df2.index,y=df2['Kings County'], mode='lines', name='Brooklyn')
fig2.add_scatter(x=df2.index,y=df2['New York County'], mode='lines', name='Manhattan')
fig2.add_scatter(x=df2.index,y=df2['Queens County'], mode='lines', name='Queens')
fig2.add_scatter(x=df2.index,y=df2['Richmond County'], mode='lines', name='Staten Island')
fig2.add_scatter(x=df2.index,y=df2['Total'], mode='lines+markers', name='NYC')
fig2.add_scatter(x=df2.index, y=df2['EMA'], mode='lines', line=dict(color='royalblue', width=4, dash='dot'), name='7 day EMA')
prepFigure(fig2, title="NYC Daily New Cases (Source: USA Facts)")
latest = df2.iloc[-1,:]
fig2.add_annotation(text="On "+latest.name.strftime("%m/%d")+":\n"+str(int(latest.Total)),
                   font=dict(family="Helvetica, Arial",size=28),
                  xref="paper", yref="paper",
                  x=1, y=1, showarrow=False)
fig2.write_json("/home/ubuntu/medtracker/medtracker/data/daily_cases.json")

#daily new deaths
df2 = DailyDeaths_df
#df2 = temp_df
fig2 = go.Figure()
fig2.add_scatter(x=df2.index,y=df2['Bronx County'], mode='lines', name='Bronx')
fig2.add_scatter(x=df2.index,y=df2['Kings County'], mode='lines', name='Brooklyn')
fig2.add_scatter(x=df2.index,y=df2['New York County'], mode='lines', name='Manhattan')
fig2.add_scatter(x=df2.index,y=df2['Queens County'], mode='lines', name='Queens')
fig2.add_scatter(x=df2.index,y=df2['Richmond County'], mode='lines', name='Staten Island')
fig2.add_scatter(x=df2.index,y=df2['Total'], mode='lines+markers', name='NYC')
fig2.add_scatter(x=df2.index, y=df2['EMA'], mode='lines', line=dict(color='royalblue', width=4, dash='dot'), name='7 day EMA')
prepFigure(fig2, title="NYC Daily Deaths (Source: USA Facts)")
fig2.write_json("/home/ubuntu/medtracker/medtracker/data/daily_deaths.json")

#hospitalizations
df2 = nyc_case_hosp_death_df
fig2 = go.Figure()
fig2.add_scatter(x=df2.index,y=df2['HOSPITALIZED_COUNT'], mode='lines', name='Hospitalizations', )
prepFigure(fig2,title="NYC New Hospitalizations (Source: NYC DOHMH)")
fig2.write_json("/home/ubuntu/medtracker/medtracker/data/hospitalizations.json")

#r0 estimation
df2 = rt_df[rt_df["region"]=="NY"].sort_values("date").set_index("date")
fig2 = go.Figure()
fig2.add_scattergl(x=df2.index,y=df2.R0_mean.where(df2.R0_mean <= 1), line={'color': 'black'}) # below threshold
fig2.add_scattergl(x=df2.index,y=df2.R0_mean.where(df2.R0_mean >= 1), line={'color': 'red'}) # Above threshhgold
fig2.add_shape( #dashed line
        type='line',
        x0=str(df2.index.min()),
        y0=1,
        x1=str(df2.index.max()),
        y1=1,
        line=dict(
            color='black',
            dash="dashdot"
        )
)
prepFigure(fig2,title="R0 estimate (Source: rt.live)")
fig2.update_layout(showlegend=False)
ro_latest = str(round(list(df2["R0_mean"])[-1],2))
fig2.add_annotation(text="Current R0:\n"+ro_latest,
                   font=dict(family="Helvetica, Arial",size=24),
                  xref="paper", yref="paper",
                  x=1, y=1, showarrow=False)
fig2.write_json("/home/ubuntu/medtracker/medtracker/data/r0_estimate.json")
