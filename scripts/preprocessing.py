import os
import argparse
import numpy as np
import pandas as pd
from pathlib import Path
from azureml.core import Run
from datetime import timedelta


def main(args):
    # Create folders
    output_path = Path(args.output_path)
    output_path.mkdir(parents=True, exist_ok=True)

    # Unload arguments
    target_lags = [int(x.strip()) for x in args.target_lags.split(',')]
    forecast_horizon = int(args.forecast_horizon)
    partitions = [x.strip() for x in args.partitions.split(',')]

    # Load the sales data
    sales = Run.get_context().input_datasets['train_data']
    df = sales.to_pandas_dataframe()

    # Create dfs for train and inference data
    train, inference = pd.DataFrame(), pd.DataFrame()

    # Get unique combinations of partitions columns
    unique_combinations = df.groupby(partitions).size().reset_index().drop(columns=0)

    # Loop through unique combinations, splitting into train and test, and adding rows for inference
    for _, row in unique_combinations.iterrows():
        # Get unique timeseries
        sub = df[(df[partitions[0]] == row[partitions[0]]) & (df[partitions[1]] == row[partitions[1]])]

        # Convert 'date' column to datetime if it's not already in datetime format
        sub[args.time_column_name] = pd.to_datetime(sub[args.time_column_name])
        
        # Sort by time column
        sub = sub.sort_values(by=args.time_column_name, ascending=True)

        # Find the maximum date in the 'date' column
        max_date = sub[args.time_column_name].max()

        # Generate new dates - 8 dates each a week after the last date
        new_dates = [max_date + timedelta(weeks=i+1) for i in range(forecast_horizon)]

        # Create a DataFrame with the new dates
        new_rows = pd.DataFrame({args.time_column_name: new_dates})

        # Append the new rows to the original DataFrame
        sub_extended = pd.concat([sub, new_rows], ignore_index=True)

        # Split data
        train = sub_extended.iloc[:-(forecast_horizon+max(target_lags))]
        inference = sub_extended.iloc[-(forecast_horizon+max(target_lags)):]

        # Add to respective dataframes
        train_df = pd.concat([train_df, train], ignore_index=True)
        inference_df = pd.concat([inference_df, inference], ignore_index=True)

    # Sort dataframes
    train_df = train_df.sort_values(by=[partitions[0], partitions[1], args.time_column_name])
    inference_df = train_df.sort_values(by=[partitions[0], partitions[1], args.time_column_name])

    # Save dfs
    if args.step == 'train':
        train.to_parquet(output_path / "oj_sales.parquet", index=False, compression=None)
    elif args.step == 'inference':
        inference.to_parquet(output_path / "oj_sales.parquet", index=False, compression=None)
    else:
        raise ValueError("Unexpected step: 'step' must be 'train' or 'inference'")


def my_parse_args():
    parser = argparse.ArgumentParser("Test")

    parser.add_argument('--step' , required=True)
    parser.add_argument('--output_path' , required=True)
    parser.add_argument('--horizon', required=True)
    parser.add_argument('--lags', required=True)
    parser.add_argument('--time_column_name', required=True)
    parser.add_argument('--label_column_name', required=True)
    parser.add_argument('--partitions', required=True)

    args = parser.parse_args()
    return args


if __name__ == "__main__":
    args = my_parse_args()
    main(args)
