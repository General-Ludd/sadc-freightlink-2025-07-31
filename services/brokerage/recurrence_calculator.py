from datetime import datetime, timedelta, date
from calendar import monthrange
from typing import List, Optional
#from services.finance.finance import get_next_billing_date

class DedicatedLanesFtlShipmentPaymentSchedule:
    def __init__(self, start_date: date, end_date: date, payment_term: str):
        self.start_date = start_date
        self.end_date = end_date
        self.payment_term = payment_term.upper().strip()

    def get_all_billing_due_dates(self) -> List[date]:
        billing_dates = []
        current_date = self.start_date.replace(day=1)

        while current_date <= self.end_date:
            dates_in_month = self._get_billing_days_for_month(current_date.year, current_date.month)
            for d in dates_in_month:
                if self.start_date <= d <= self.end_date:
                    billing_dates.append(d)

            # move to first day of next month
            if current_date.month == 12:
                current_date = current_date.replace(year=current_date.year + 1, month=1)
            else:
                current_date = current_date.replace(month=current_date.month + 1)

        return billing_dates

    def _get_billing_days_for_month(self, year: int, month: int) -> List[date]:
        last_day = monthrange(year, month)[1]
        billing_days = []

        if self.payment_term == "NET 7":
            billing_days = [7, 14, 21, 28]
        elif self.payment_term == "NET 10":
            billing_days = [10, 20, last_day]
        elif self.payment_term == "NET 15":
            billing_days = [15, last_day]
        elif self.payment_term == "EOM":
            billing_days = [last_day]
        else:
            raise ValueError(f"Unsupported payment term: {self.payment_term}")

        return [date(year, month, min(day, last_day)) for day in billing_days]


class RecurrenceCalculator:
    def __init__(self, recurrence_frequency: str, recurrence_days: List[str], start_date: date,
                 end_date: Optional[date] = None, shipments_per_interval: int = 1, skip_weekends: bool = False):
        self.recurrence_frequency = recurrence_frequency
        self.recurrence_days = recurrence_days
        self.start_date = start_date
        self.end_date = end_date
        self.shipments_per_interval = shipments_per_interval
        self.skip_weekends = skip_weekends
        self.day_map = {
            "Monday": 0,
            "Tuesday": 1,
            "Wednesday": 2,
            "Thursday": 3,
            "Friday": 4,
            "Saturday": 5,
            "Sunday": 6
        }

    def get_recurrence_dates(self, total_shipments: int) -> List[date]:
        dates = []
        current_date = self.start_date
        shipments_generated = 0

        recurrence_days_index = [self.day_map[day] for day in self.recurrence_days]

        if self.recurrence_frequency == "Daily":
            while shipments_generated < total_shipments:
                if current_date.weekday() in recurrence_days_index:
                    if not (self.skip_weekends and current_date.weekday() in (5, 6)):
                        dates.append(current_date)
                        shipments_generated += 1
                current_date += timedelta(days=1)
                if self.end_date and current_date > self.end_date:
                    break

        elif self.recurrence_frequency == "Weekly":
            while shipments_generated < total_shipments:
                for i in range(7):  # 7-day weekly interval
                    potential_date = current_date + timedelta(days=i)
                    if potential_date.weekday() in recurrence_days_index:
                        if self.skip_weekends and potential_date.weekday() in (5, 6):
                            continue
                        if self.end_date and potential_date > self.end_date:
                            return dates
                        if shipments_generated >= total_shipments:
                            return dates
                        dates.append(potential_date)
                        shipments_generated += 1
                current_date += timedelta(days=7)

        else:
            raise ValueError("Unsupported recurrence frequency. Only 'Daily' and 'Weekly' are supported.")

        return dates

    def calculate_total_shipments(self, total_shipments: int) -> int:
        """
        Calculate the total number of shipments in the contract.
        """
        shipment_dates = self.get_recurrence_dates(total_shipments)
        return len(shipment_dates) * self.shipments_per_interval