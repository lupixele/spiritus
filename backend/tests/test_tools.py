"""Unit tests for Spiritus Tool Registry and Generic Tools."""
import asyncio
import unittest

from core.tools import CalculatorTool, DatasetLookupTool, KeyValueStoreTool, ToolRegistry, ToolResult


class TestSpiritusTools(unittest.TestCase):
    def setUp(self):
        self.registry = ToolRegistry()
        self.calc = CalculatorTool()
        self.lookup = DatasetLookupTool()
        self.kv = KeyValueStoreTool()

        self.registry.register(self.calc)
        self.registry.register(self.lookup)
        self.registry.register(self.kv)

    def test_calculator_arithmetic(self):
        res = asyncio.run(self.calc.run(expression="10 + 20 * 3"))
        self.assertTrue(res.success)
        self.assertEqual(res.output, 70)

        res_pow = asyncio.run(self.calc.run(expression="2 ** 8"))
        self.assertTrue(res_pow.success)
        self.assertEqual(res_pow.output, 256)

    def test_calculator_safety_bounds(self):
        res_empty = asyncio.run(self.calc.run(expression=""))
        self.assertFalse(res_empty.success)

        res_illegal = asyncio.run(self.calc.run(expression="__import__('os').system('ls')"))
        self.assertFalse(res_illegal.success)

    def test_dataset_lookup(self):
        res_list = asyncio.run(self.lookup.run(collection="services"))
        self.assertTrue(res_list.success)
        self.assertGreaterEqual(len(res_list.output), 1)

        res_key = asyncio.run(self.lookup.run(collection="services", key="srv_01"))
        self.assertTrue(res_key.success)
        self.assertEqual(res_key.output["name"], "Primary Dispatch")

        res_filtered = asyncio.run(self.lookup.run(collection="services", filter_field="status", filter_value="active"))
        self.assertTrue(res_filtered.success)
        self.assertTrue(all(item["status"] == "active" for item in res_filtered.output))

    def test_kv_store(self):
        # Set
        res_set = asyncio.run(self.kv.run(action="set", key="target_quota", value="500"))
        self.assertTrue(res_set.success)

        # Get
        res_get = asyncio.run(self.kv.run(action="get", key="target_quota"))
        self.assertTrue(res_get.success)
        self.assertEqual(res_get.output, "500")

        # List
        res_list = asyncio.run(self.kv.run(action="list"))
        self.assertTrue(res_list.success)
        self.assertIn("target_quota", res_list.output)


if __name__ == "__main__":
    unittest.main()
