import time
import traceback
from datetime import datetime, timedelta
import concurrent.futures
import ryanair.types
from ryanair import Ryanair


class ConnectionFlight:
    def __init__(self, *flights: ryanair.types.Flight):
        self.total_price = sum(f.price for f in flights)
        self.flights = flights

class ReturnFare:
    def __init__(self, outbound: ConnectionFlight, inbound: ConnectionFlight):
        self.total_price = inbound.total_price + outbound.total_price
        self.inbound = inbound
        self.outbound = outbound

def search_ryanair_with_return():
    ryanair = Ryanair("EUR")  # Euro currency, so could also be USD, GBP, etc...

    results = dict()
    start_date = datetime(year=2023, month=8, day=1)
    end_date = datetime(year=2023, month=9, day=30)
    current_date = start_date
    while current_date <= end_date:
        weekday = current_date.strftime("%A")
        delta = 6 if weekday == "Thursday" else 1
        departure_date = current_date.strftime('%Y-%m-%d')
        return_date_from = (current_date + timedelta(days=7)).strftime('%Y-%m-%d')
        return_date_to = (current_date + timedelta(days=10)).strftime('%Y-%m-%d')
        try:
            trips = ryanair.get_return_flights(
                source_airport="TLV",
                date_from=departure_date,
                date_to=departure_date,
                return_date_from=return_date_from,
                return_date_to=return_date_to,
            )
            trips = [trip for trip in trips if
                     trip.totalPrice <= 2 * max_price_per_direction and trip.outbound.destination not in exclude_dests]
            results[departure_date] = trips
        except Exception:
            traceback.print_exc()
        finally:
            current_date += timedelta(days=delta)
    # pretty(results)
    return results


def search_ryanair_one_way(source_airport_code: str,
                           earliest_departure: datetime, latest_departure: datetime,
                           dest_country_code: str = None, dest_airport_code: str = None,
                           max_price: int = 1000):
    ryanair = Ryanair("EUR")  # Euro currency, so could also be USD, GBP, etc...

    results = dict()
    current_date = earliest_departure
    while current_date <= latest_departure:
        departure_date = current_date.strftime('%Y-%m-%d')
        try:
            flights = ryanair.get_flights(
                airport=source_airport_code,
                date_from=departure_date,
                date_to=departure_date,
                destination_country=dest_country_code
            )

            flights = [
                flight for flight in flights
                if flight.price <= max_price
                and (flight.destination == dest_airport_code or not dest_country_code)
            ]
            results[departure_date] = flights
        except Exception:
            traceback.print_exc()
        finally:
            current_date += timedelta(days=1)
    # pretty(results)
    return results


def ryanair_one_way_with_dest(source_airport_code, earliest_departure, latest_departure, dest_country_code,
                              dest_airport_code, max_price):
    results = dict()
    first_flights = search_ryanair_one_way(
        source_airport_code=source_airport_code,
        earliest_departure=earliest_departure,
        latest_departure=latest_departure
    )

    def search_second_flights(first_flight, first_flight_date, connection_airport, connection_date,
                              second_flight_max_price):
        second_flights_options = search_ryanair_one_way(
            source_airport_code=connection_airport,
            earliest_departure=connection_date,
            latest_departure=connection_date + timedelta(days=1),
            dest_country_code=dest_country_code,
            dest_airport_code=dest_airport_code,
            max_price=second_flight_max_price
        )
        trips = dict()
        for second_flight_date, second_flights in second_flights_options.items():
            if second_flights:
                trips[second_flight_date] = [ConnectionFlight(first_flight, second_flight) for
                                             second_flight in second_flights]
        return trips

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        tasks = []
        for first_flight_date, flights_per_date in first_flights.items():
            for first_flight in flights_per_date:
                connection_airport = first_flight.destination
                connection_date = first_flight.departureTime
                second_flight_max_price = max_price - first_flight.price
                tasks.append(executor.submit(search_second_flights, first_flight, first_flight_date, connection_airport,
                                             connection_date, second_flight_max_price))
        for task in concurrent.futures.as_completed(tasks):
            result = task.result()
            for k, v in result.items():
                if k in results:
                    results[k] += v
                else:
                    results[k] = v
            if task.exception() is not None:
                traceback.print_exc()

    # pretty(results)
    return results


def ryanair_return_with_dest(source_airport_code, source_country_code, earliest_departure, latest_departure,
                             dest_airport_code, dest_country_code, max_price, min_days, max_days):
    results = dict()
    outbounds = ryanair_one_way_with_dest(
        source_airport_code=source_airport_code,
        earliest_departure=earliest_departure,
        latest_departure=latest_departure,
        dest_country_code=dest_country_code,
        dest_airport_code=dest_airport_code,
        max_price=max_price
    )
    print(f"done outbounds. found {sum(len(outbound) for outbound in outbounds)} outbounds")
    pretty(outbounds)
    inbounds = ryanair_one_way_with_dest(
        source_airport_code=dest_airport_code,
        earliest_departure=earliest_departure + timedelta(days=min_days),
        latest_departure=latest_departure + timedelta(days=max_days),
        dest_country_code=source_country_code,
        dest_airport_code=source_airport_code,
        max_price=max_price
    )
    print(f"done inbounds. found {sum(len(inbound) for inbound in inbounds)} inbounds")
    for outbound_date, outbounds_per_date in outbounds.items():
        od = datetime.strptime(outbound_date, '%Y-%m-%d')
        inbound_dates = {(od + timedelta(i)).strftime('%Y-%m-%d') for i in range(min_days, max_days)}
        relevant_inbounds = {d: inbound for d, inbound in inbounds.items() if d in inbound_dates}
        trips = [
            ReturnFare(outbound, inbound)
            for outbound in outbounds_per_date
            for _, inbound in relevant_inbounds
            if outbound.total_price + inbound.total_price <= max_price
        ]
        results[outbound_date] = trips
        print("Done with", outbound_date)
    pretty(results)
    return results


def pretty(d, indent=0):
    if isinstance(d, ryanair.types.Trip) or isinstance(d, ryanair.types.Flight):
        pretty(dict(d._asdict()), indent + 1)
        print()
    elif isinstance(d, ConnectionFlight):
        print('\t' * indent + "Fare Total Price: ", d.total_price)
        for flight in d.flights:
            print('\t' * indent + flight.departureTime.strftime("%Y-%m-%d"))
            pretty(dict(flight._asdict()), indent + 1)
    elif not isinstance(d, dict):
        print('\t' * indent + str(d))
    else:
        for key, value in d.items():
            if not value:
                continue
            if isinstance(value, dict):
                print('\t' * indent + str(key))
                pretty(value, indent + 1)
            elif isinstance(value, list):
                print('\t' * indent + str(key))
                for elem in value:
                    pretty(elem, indent + 1)
            elif isinstance(value, ryanair.types.Flight):
                print('\t' * indent + str(key))
                pretty(dict(value._asdict()), indent + 1)
            else:
                print('\t' * indent + str(key) + ": " + str(value))


def main():
    start_date = datetime(year=2023, month=8, day=25)
    end_date = datetime(year=2023, month=9, day=10)
    res = ryanair_return_with_dest(
        source_airport_code="TLV",
        source_country_code="IL",
        earliest_departure=start_date,
        latest_departure=end_date,
        dest_country_code="PT",
        dest_airport_code="LIS",
        max_price=110,
        min_days=7,
        max_days=10
    )
    print("h")



if __name__ == '__main__':
    main()
