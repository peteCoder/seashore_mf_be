"""
Loan Calculator Utility
Implements flat rate interest calculation with tiered pricing based on frequency and duration
"""

from decimal import Decimal
from datetime import datetime, timedelta
from typing import Dict, Tuple


class LoanCalculator:
    """
    Calculates loan details using flat rate method with tiered interest rates.
    Interest rates vary based on repayment frequency and loan duration.
    """
    
    # Tiered interest rates (monthly rates)
    INTEREST_RATES = {
        'daily': {
            '1-30': Decimal('0.10'),      # 10% per month for 1-30 days
            '31-90': Decimal('0.08'),     # 8% per month for 31-90 days
            '91-180': Decimal('0.07'),    # 7% per month for 91-180 days
            '181+': Decimal('0.06'),      # 6% per month for 181+ days
        },
        'weekly': {
            '1-12': Decimal('0.09'),      # 9% per month for 1-12 weeks
            '13-26': Decimal('0.07'),     # 7% per month for 13-26 weeks
            '27-52': Decimal('0.06'),     # 6% per month for 27-52 weeks
            '53+': Decimal('0.05'),       # 5% per month for 53+ weeks
        },
        'monthly': {
            '1-3': Decimal('0.08'),       # 8% per month for 1-3 months
            '4-6': Decimal('0.06'),       # 6% per month for 4-6 months
            '7-12': Decimal('0.05'),      # 5% per month for 7-12 months
            '13+': Decimal('0.04'),       # 4% per month for 13+ months
        },
        'biweekly': {
            '1-12': Decimal('0.08'),      # 8% per month for 1-12 periods (6 months)
            '13-24': Decimal('0.06'),     # 6% per month for 13-24 periods (12 months)
            '25+': Decimal('0.05'),       # 5% per month for 25+ periods
        }
    }
    
    @classmethod
    def get_interest_rate(cls, frequency: str, duration_value: int) -> Decimal:
        """
        Get the applicable monthly interest rate based on frequency and duration.
        
        Args:
            frequency: Repayment frequency ('daily', 'weekly', 'monthly', 'biweekly')
            duration_value: Number of periods
            
        Returns:
            Monthly interest rate as Decimal
        """
        if frequency not in cls.INTEREST_RATES:
            raise ValueError(f"Invalid frequency: {frequency}")
        
        tiers = cls.INTEREST_RATES[frequency]
        
        # Find the applicable tier
        for tier_range, rate in tiers.items():
            if '+' in tier_range:
                # e.g., "181+" or "13+"
                min_value = int(tier_range.replace('+', ''))
                if duration_value >= min_value:
                    return rate
            else:
                # e.g., "1-30" or "4-6"
                min_val, max_val = map(int, tier_range.split('-'))
                if min_val <= duration_value <= max_val:
                    return rate
        
        # Default to highest tier rate if not found
        return list(tiers.values())[-1]
    
    @classmethod
    def convert_to_months(cls, frequency: str, duration_value: int) -> Decimal:
        """
        Convert duration to months based on frequency.
        
        Args:
            frequency: Repayment frequency
            duration_value: Number of periods
            
        Returns:
            Duration in months as Decimal
        """
        conversions = {
            'daily': Decimal(duration_value) / Decimal('30'),  # Approx 30 days/month
            'weekly': Decimal(duration_value) / Decimal('4.33'),  # Approx 4.33 weeks/month
            'biweekly': Decimal(duration_value) / Decimal('2.17'),  # Approx 2.17 biweeks/month
            'monthly': Decimal(duration_value),
        }
        
        return conversions.get(frequency, Decimal(duration_value))
    
    @classmethod
    def calculate_loan(
        cls,
        principal_amount: Decimal,
        frequency: str,
        duration_value: int,
        start_date: datetime = None
    ) -> Dict:
        """
        Calculate complete loan details using flat rate method.
        
        Formula:
            Total Interest = Principal × Monthly Rate × Duration in Months
            Total Amount = Principal + Total Interest
            Installment = Total Amount / Number of Installments
        
        Args:
            principal_amount: Loan principal amount
            frequency: Repayment frequency
            duration_value: Number of periods (days, weeks, or months)
            start_date: Loan start date (defaults to today)
            
        Returns:
            Dictionary with complete loan calculation details
        """
        if principal_amount <= 0:
            raise ValueError("Principal amount must be greater than zero")
        
        if duration_value <= 0:
            raise ValueError("Duration must be greater than zero")
        
        # Get the applicable monthly interest rate
        monthly_rate = cls.get_interest_rate(frequency, duration_value)
        
        # Convert duration to months
        duration_months = cls.convert_to_months(frequency, duration_value)
        
        # Calculate using flat rate: Total Interest = P × r × t
        total_interest = principal_amount * monthly_rate * duration_months
        total_amount = principal_amount + total_interest
        
        # Calculate installment amount
        num_installments = duration_value
        installment_amount = total_amount / Decimal(num_installments)
        
        # Calculate dates
        if start_date is None:
            start_date = datetime.now().date()
        elif isinstance(start_date, datetime):
            start_date = start_date.date()
        
        first_payment_date = cls.calculate_next_payment_date(start_date, frequency)
        final_payment_date = cls.calculate_final_payment_date(
            start_date, frequency, duration_value
        )
        
        # Annual interest rate for display
        annual_rate = monthly_rate * Decimal('12') * Decimal('100')  # Convert to percentage
        
        return {
            'principal_amount': principal_amount,
            'monthly_interest_rate': monthly_rate,
            'annual_interest_rate': annual_rate,
            'duration_value': duration_value,
            'duration_months': duration_months,
            'repayment_frequency': frequency,
            'total_interest': total_interest,
            'total_repayment': total_amount,
            'installment_amount': installment_amount,
            'number_of_installments': num_installments,
            'first_payment_date': first_payment_date,
            'final_payment_date': final_payment_date,
            'outstanding_balance': total_amount,  # Initially equals total amount
        }
    
    @classmethod
    def calculate_next_payment_date(
        cls,
        current_date: datetime.date,
        frequency: str
    ) -> datetime.date:
        """Calculate the next payment date based on frequency."""
        if frequency == 'daily':
            return current_date + timedelta(days=1)
        elif frequency == 'weekly':
            return current_date + timedelta(weeks=1)
        elif frequency == 'biweekly':
            return current_date + timedelta(weeks=2)
        elif frequency == 'monthly':
            # Add one month
            if current_date.month == 12:
                return current_date.replace(year=current_date.year + 1, month=1)
            else:
                return current_date.replace(month=current_date.month + 1)
        else:
            return current_date + timedelta(days=30)
    
    @classmethod
    def calculate_final_payment_date(
        cls,
        start_date: datetime.date,
        frequency: str,
        duration_value: int
    ) -> datetime.date:
        """Calculate the final payment date."""
        if frequency == 'daily':
            return start_date + timedelta(days=duration_value)
        elif frequency == 'weekly':
            return start_date + timedelta(weeks=duration_value)
        elif frequency == 'biweekly':
            return start_date + timedelta(weeks=duration_value * 2)
        elif frequency == 'monthly':
            # Add duration_value months
            months = duration_value
            years = months // 12
            remaining_months = months % 12
            
            new_year = start_date.year + years
            new_month = start_date.month + remaining_months
            
            if new_month > 12:
                new_year += 1
                new_month -= 12
            
            # Handle day overflow (e.g., Jan 31 + 1 month = Feb 28/29)
            try:
                return start_date.replace(year=new_year, month=new_month)
            except ValueError:
                # Day doesn't exist in target month, use last day of month
                if new_month == 12:
                    return datetime(new_year + 1, 1, 1).date() - timedelta(days=1)
                else:
                    return datetime(new_year, new_month + 1, 1).date() - timedelta(days=1)
        else:
            return start_date + timedelta(days=duration_value * 30)
    
    @classmethod
    def generate_repayment_schedule(
        cls,
        principal_amount: Decimal,
        frequency: str,
        duration_value: int,
        start_date: datetime = None
    ) -> list:
        """
        Generate a detailed repayment schedule.
        
        Returns:
            List of dictionaries with repayment schedule details
        """
        loan_details = cls.calculate_loan(
            principal_amount, frequency, duration_value, start_date
        )
        
        schedule = []
        remaining_balance = loan_details['total_repayment']
        current_date = loan_details['first_payment_date']
        
        for i in range(1, duration_value + 1):
            payment_amount = loan_details['installment_amount']
            remaining_balance -= payment_amount
            
            schedule.append({
                'installment_number': i,
                'due_date': current_date,
                'installment_amount': payment_amount,
                'balance_after_payment': max(remaining_balance, Decimal('0')),
                'status': 'pending',
            })
            
            # Calculate next payment date
            current_date = cls.calculate_next_payment_date(current_date, frequency)
        
        return schedule
    
    @classmethod
    def get_rate_info_for_ui(cls, frequency: str) -> list:
        """
        Get interest rate information formatted for UI display.
        
        Returns:
            List of dictionaries with tier information
        """
        if frequency not in cls.INTEREST_RATES:
            return []
        
        tiers = cls.INTEREST_RATES[frequency]
        result = []
        
        for tier_range, rate in tiers.items():
            monthly_rate = float(rate * 100)  # Convert to percentage
            annual_rate = monthly_rate * 12
            
            result.append({
                'range': tier_range,
                'monthly_rate': f"{monthly_rate:.1f}%",
                'annual_rate': f"{annual_rate:.1f}%",
            })
        
        return result


# Example usage and tests
if __name__ == "__main__":
    # Test case 1: Daily loan for 30 days
    print("=== Test 1: Daily Loan (30 days) ===")
    result = LoanCalculator.calculate_loan(
        principal_amount=Decimal('50000'),
        frequency='daily',
        duration_value=30
    )
    print(f"Principal: ₦{result['principal_amount']:,.2f}")
    print(f"Monthly Rate: {result['monthly_interest_rate'] * 100}%")
    print(f"Total Interest: ₦{result['total_interest']:,.2f}")
    print(f"Total Repayment: ₦{result['total_repayment']:,.2f}")
    print(f"Daily Payment: ₦{result['installment_amount']:,.2f}")
    print()
    
    # Test case 2: Weekly loan for 20 weeks
    print("=== Test 2: Weekly Loan (20 weeks) ===")
    result = LoanCalculator.calculate_loan(
        principal_amount=Decimal('100000'),
        frequency='weekly',
        duration_value=20
    )
    print(f"Principal: ₦{result['principal_amount']:,.2f}")
    print(f"Monthly Rate: {result['monthly_interest_rate'] * 100}%")
    print(f"Duration in Months: {result['duration_months']:.2f}")
    print(f"Total Interest: ₦{result['total_interest']:,.2f}")
    print(f"Total Repayment: ₦{result['total_repayment']:,.2f}")
    print(f"Weekly Payment: ₦{result['installment_amount']:,.2f}")
    print()
    
    # Test case 3: Monthly loan for 12 months
    print("=== Test 3: Monthly Loan (12 months) ===")
    result = LoanCalculator.calculate_loan(
        principal_amount=Decimal('200000'),
        frequency='monthly',
        duration_value=12
    )
    print(f"Principal: ₦{result['principal_amount']:,.2f}")
    print(f"Monthly Rate: {result['monthly_interest_rate'] * 100}%")
    print(f"Annual Rate: {result['annual_interest_rate']:.1f}%")
    print(f"Total Interest: ₦{result['total_interest']:,.2f}")
    print(f"Total Repayment: ₦{result['total_repayment']:,.2f}")
    print(f"Monthly Payment: ₦{result['installment_amount']:,.2f}")
    print()
    
    # Test case 4: Show rate tiers
    print("=== Rate Tiers for Monthly Frequency ===")
    tiers = LoanCalculator.get_rate_info_for_ui('monthly')
    for tier in tiers:
        print(f"{tier['range']}: {tier['monthly_rate']} per month ({tier['annual_rate']} annual)")