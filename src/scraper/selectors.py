"""
Google Maps DOM Selectors Configuration.
Isolating DOM selectors from class implementation code allows easy fixes
when Google changes class names or HTML structures.
"""

# Selectors list panel and search inputs
SEARCH_INPUT = 'input[name="q"], input#searchboxinput, input[aria-label*="Search"]'
SEARCH_BUTTON = "button#searchbox-searchbutton"
RESULTS_LIST_PANEL = 'div[role="feed"]'
BUSINESS_CARD_LINK = 'a[href*="/maps/place/"]'

# Selectors inside individual business details page/panel
BUSINESS_NAME = "h1.DUwDvf"
BUSINESS_RATING_CONTAINER = "div.F7nice"
BUSINESS_RATING = "span.MW4etd"
BUSINESS_CATEGORY = 'button[jsaction*="category"]'
BUSINESS_ADDRESS = '[data-item-id="address"]'
BUSINESS_PHONE = '[data-item-id^="phone:tel:"]'
BUSINESS_WEBSITE = '[data-item-id="authority"]'
