"""Expected no-odds days are deferred without publishing an empty daily edition."""
WAITING_FOR_ODDS = 'waitingForOddsV51'


def no_supported_prices(snapshot):
    status = snapshot.get('dataStatus') or {}
    coverage = snapshot.get('coverage') or {}
    discovery = status.get('matchdayDiscovery') or {}
    return (status.get('fixtures') == 'ok' and status.get('odds') == 'empty'
            and (status.get('oddsBudgetLimited') is True
                 or status.get('successfulOddsRequests', 0) > 0
                 or status.get('requestedLeagues') == [] and discovery.get('catalogAvailable') is True)
            and coverage.get('matchedOdds') == 0)
