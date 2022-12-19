import json
from pprint import pprint
import traceback
from datetime import datetime, timedelta

import ryanair.types
from ryanair import Ryanair

exclude_dests = {"PFO", "NAP", "OTP", "MLA", "POZ"}
max_price = 80


def search_ryanair():
    ryanair = Ryanair("EUR")  # Euro currency, so could also be USD, GBP, etc...

    results = dict()
    start_date = datetime(year=2022, month=12, day=20)
    end_date = datetime(year=2023, month=6, day=1)
    current_date = start_date
    while current_date <= end_date:
        weekday = current_date.weekday()
        delta = 6 if weekday == 3 else 1
        if weekday not in {2, 3}:
            current_date += timedelta(days=delta)
            continue
        departure_date = current_date.strftime('%Y-%m-%d')
        return_date = (current_date + timedelta(days=3)).strftime('%Y-%m-%d')
        try:
            trips = ryanair.get_return_flights(
                source_airport="TLV",
                date_from=departure_date,
                date_to=departure_date,
                return_date_from=return_date,
                return_date_to=return_date,
            )
            trips = [trip for trip in trips if trip.totalPrice <= max_price and trip.outbound.destination not in exclude_dests]
            results[departure_date] = trips
        except Exception:
            traceback.print_exc()
        finally:
            current_date += timedelta(days=delta)
    pretty(results)


def pretty(d, indent=0):
    if isinstance(d, ryanair.types.Trip) or isinstance(d, ryanair.types.Flight):
        pretty(dict(d._asdict()), indent+1)
    elif not isinstance(d, dict):
        print('\t' * indent + d)
    else:
        for key, value in d.items():
            if not value:
                continue
            if isinstance(value, dict):
                print('\t' * indent + str(key))
                pretty(value, indent+1)
            elif isinstance(value, list):
                print('\t' * indent + str(key))
                for elem in value:
                    pretty(elem, indent+1)
            elif isinstance(value, ryanair.types.Flight):
                print('\t' * indent + str(key))
                pretty(dict(value._asdict()), indent + 1)
            else:
                print('\t' * indent + str(key) + ": " + str(value))


def main():
    search_ryanair()


if __name__ == '__main__':
    main()
