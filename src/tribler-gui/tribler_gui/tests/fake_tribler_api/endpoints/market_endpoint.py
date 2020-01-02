from aiohttp import web

from tribler_core.restapi.rest_endpoint import RESTEndpoint, RESTResponse

from tribler_gui.tests.fake_tribler_api import tribler_utils


class MarketEndpoint(RESTEndpoint):
    """
    This class represents the root endpoint of the market community API where we trade reputation.
    """

    def setup_routes(self):
        self.app.add_routes(
            [
                web.get('/asks', self.get_asks),
                web.get('/bids', self.get_bids),
                web.get('/transactions', self.get_transactions),
                web.get('/transactions/{trader_id}/{transaction_id}', self.get_payments),
                web.get('/orders', self.get_orders),
            ]
        )

    async def get_asks(self, _):
        return RESTResponse(
            {
                "asks": [
                    {
                        "asset1": "DUM1",
                        "asset2": "DUM2",
                        "ticks": [tick.get_json() for tick in tribler_utils.tribler_data.order_book['asks']],
                    }
                ]
            }
        )

    async def get_bids(self, _):
        return RESTResponse(
            {
                "bids": [
                    {
                        "asset1": "DUM1",
                        "asset2": "DUM2",
                        "ticks": [tick.get_json() for tick in tribler_utils.tribler_data.order_book['bids']],
                    }
                ]
            }
        )

    async def get_transactions(self, _):
        return RESTResponse(
            {"transactions": [transaction.get_json() for transaction in tribler_utils.tribler_data.transactions]}
        )

    async def get_payments(self, request):
        trader_id = request.match_info['trader_id']
        transaction_id = int(request.match_info['transaction_id'])
        tx = tribler_utils.tribler_data.get_transaction(trader_id, transaction_id)
        return RESTResponse({"payments": [payment.get_json() for payment in tx.payments]})

    async def get_orders(self, _):
        return RESTResponse({"orders": [order.get_json() for order in tribler_utils.tribler_data.orders]})
