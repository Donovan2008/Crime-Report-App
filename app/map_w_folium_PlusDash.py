import sys
import os
import logging
import pandas as pd
import folium
from folium.plugins import HeatMap, MarkerCluster
from dash import Dash, dcc, html
from dash.dependencies import Input, Output
from datetime import datetime

# Configure logging
logging.basicConfig(filename='app.log', level=logging.DEBUG,
                    format='%(asctime)s - %(levelname)s - %(message)s')

logging.info("Starting the Dash application")

def main():
    try:
        # Load the CSV file
        csv_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'updated_parsed_events_data_with_lat_long.csv')
        logging.info(f"Loading CSV file from {csv_path}")
        df = pd.read_csv(csv_path)

        # Convert 'Event Date / Time' to datetime
        df['Event Date / Time'] = pd.to_datetime(df['Event Date / Time'])
        logging.info("CSV file loaded and processed")

        # Determine if the event is on a weekend
        df['Weekend'] = df['Event Date / Time'].dt.weekday >= 5

        # Separate the data for "7XX W MAIN Belleville, IL" and other locations
        main_address = '7XX W MAIN Belleville, IL'
        main_address_data = df[df['Address'] == main_address]
        other_data = df[df['Address'] != main_address]

        # Function to generate the Folium map with HeatMap and MarkerCluster
        def create_map(data, main_data):
            logging.info("Creating map")
            m = folium.Map(location=[38.52, -89.98], zoom_start=13)
            
            # Add MarkerCluster
            marker_cluster = MarkerCluster().add_to(m)
            
            # Add HeatMap
            heat_data = [[row['Latitude'], row['Longitude']] for index, row in data.iterrows() if not pd.isnull(row['Latitude']) and not pd.isnull(row['Longitude'])]
            HeatMap(heat_data).add_to(m)
            
            # Aggregate data by address and count occurrences
            address_counts = data['Address'].value_counts()
            for address, count in address_counts.items():
                location_data = data[data['Address'] == address].iloc[0]
                if not pd.isnull(location_data['Latitude']) and not pd.isnull(location_data['Longitude']):
                    folium.Marker(
                        location=[location_data['Latitude'], location_data['Longitude']],
                        popup=folium.Popup(f"<b>Address:</b> {address}<br><b>Reports:</b> {count}<br><b>Type:</b> {location_data['Type']}"),
                        icon=folium.Icon(color='blue', icon='info-sign')
                    ).add_to(marker_cluster)

            # Add a separate marker for "7XX W MAIN Belleville, IL"
            if not main_data.empty:
                main_location = [main_data.iloc[0]['Latitude'], main_data.iloc[0]['Longitude']]
                folium.Marker(
                    location=main_location,
                    popup=folium.Popup(f"<b>Police Station (7XX W MAIN)</b><br><b>Reports:</b> {len(main_data)}<br><b>Type:</b> {main_data.iloc[0]['Type']}"),
                    icon=folium.Icon(color='red', icon='info-sign')
                ).add_to(m)

            logging.info("Map created")
            return m._repr_html_()

        # Function to generate the report table
        def generate_report_table(data):
            logging.info("Generating report table")
            return html.Table([
                html.Thead(html.Tr([html.Th(col) for col in data.columns])),
                html.Tbody([
                    html.Tr([
                        html.Td(data.iloc[i][col]) for col in data.columns
                    ]) for i in range(len(data))
                ])
            ])

        # Initialize the Dash app
        logging.info("Initializing Dash app")
        app = Dash(__name__)

        # Layout of the Dash app
        app.layout = html.Div([
            html.H1("Belleville Police Department Calls for Service"),
            html.Div([
                html.Div([
                    html.Label("Filter by Event Type"),
                    dcc.Dropdown(
                        id='event-type-dropdown',
                        options=[{'label': event_type, 'value': event_type} for event_type in df['Type'].unique()],
                        multi=True,
                        placeholder="Select event types"
                    )
                ], style={'width': '30%', 'display': 'inline-block'}),
                html.Div([
                    html.Label("Filter by Date"),
                    dcc.DatePickerRange(
                        id='date-picker-range',
                        start_date=df['Event Date / Time'].min(),
                        end_date=df['Event Date / Time'].max(),
                        display_format='Y-M-D'
                    )
                ], style={'width': '30%', 'display': 'inline-block', 'margin-left': '50px'}),
                html.Div([
                    html.Label("Filter by Weekend"),
                    dcc.RadioItems(
                        id='weekend-radio',
                        options=[
                            {'label': 'Both', 'value': 'both'},
                            {'label': 'Weekday', 'value': 'weekday'},
                            {'label': 'Weekend', 'value': 'weekend'}
                        ],
                        value='both',
                        labelStyle={'display': 'inline-block'}
                    )
                ], style={'width': '30%', 'display': 'inline-block', 'margin-left': '50px'})
            ]),
            html.Div([
                html.Iframe(id='map', srcDoc=create_map(other_data, main_address_data), width='100%', height='800')
            ], style={'width': '100%', 'display': 'inline-block', 'padding': '20px'}),
            html.H2("Event Reports"),
            html.Div(id='report-table', style={'height': '300px', 'overflowY': 'scroll'})
        ])

        # Callback to update the map and table based on filters
        @app.callback(
            [Output('map', 'srcDoc'), Output('report-table', 'children')],
            [Input('event-type-dropdown', 'value'), Input('date-picker-range', 'start_date'), Input('date-picker-range', 'end_date'), Input('weekend-radio', 'value')]
        )
        def update_dashboard(event_types, start_date, end_date, weekend_value):
            filtered_df = other_data.copy()
            if event_types:
                filtered_df = filtered_df[filtered_df['Type'].isin(event_types)]
            if start_date and end_date:
                filtered_df = filtered_df[(filtered_df['Event Date / Time'] >= start_date) & (filtered_df['Event Date / Time'] <= end_date)]
            if weekend_value != 'both':
                is_weekend = weekend_value == 'weekend'
                filtered_df = filtered_df[filtered_df['Weekend'] == is_weekend]
            
            # Update map
            updated_map = create_map(filtered_df, main_address_data)
            
            # Update report table
            report_table = generate_report_table(filtered_df)
            
            return updated_map, report_table

        if __name__ == '__main__':
            logging.info("Starting server")
            debug_mode = not hasattr(sys, 'frozen')
            app.run_server(debug=debug_mode, host='127.0.0.1', port=8050)
            logging.info("Server running")

    except Exception as e:
        logging.error(f"An error occurred: {e}")
        raise

if __name__ == '__main__':
    main()
