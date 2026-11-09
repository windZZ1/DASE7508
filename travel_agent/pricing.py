"""Calculate one-night hotel prices and eligible coupon quotes."""

from datetime import date


def calculate_quotes(hotel, coupons, check_in):
    """
    Return the no-coupon quote and all eligible coupon quotes.

    Prices are integer cents and already include taxes and fees.
    Coupon validity is checked against the check-in date, inclusively.
    Only one coupon can be used for each quote.
    """
    base_price = hotel["base_price_cents"]

    if type(base_price) is not int or base_price < 0:
        raise ValueError("base_price_cents must be a nonnegative integer")

    check_in_date = date.fromisoformat(check_in)

    quotes = [
        {
            "coupon_code": None,
            "total_cents": base_price,
        }
    ]

    for coupon in coupons:
        # A coupon may only be used for its assigned hotel.
        if coupon["hotel_id"] != hotel["hotel_id"]:
            continue

        valid_from = date.fromisoformat(coupon["valid_from"])
        valid_until = date.fromisoformat(coupon["valid_until"])

        if not valid_from <= check_in_date <= valid_until:
            continue

        discount = coupon["discount_cents"]
        if type(discount) is not int or discount < 0:
            raise ValueError("discount_cents must be a nonnegative integer")

        # The final price cannot be less than zero.
        total = max(0, base_price - discount)

        quotes.append(
            {
                "coupon_code": coupon["coupon_code"],
                "total_cents": total,
            }
        )

    return quotes