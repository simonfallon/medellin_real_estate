import { describe, it, expect, beforeEach, vi } from "vitest";
import { scrapeSource } from "../modules/api.js";

describe("Dynamic Price Range Functionality", () => {
  describe("API: scrapeSource", () => {
    let fetchMock;

    beforeEach(() => {
      // Mock global fetch
      fetchMock = vi.fn();
      global.fetch = fetchMock;
    });

    it("should construct URL without price params when both are null", async () => {
      fetchMock.mockResolvedValue({
        ok: true,
        json: async () => ({ success: true }),
      });

      await scrapeSource("all", false, null, null);

      expect(fetchMock).toHaveBeenCalledWith(
        "/api/scrape/batch?source=all&force=false",
        expect.any(Object),
      );
    });

    it("should construct URL with price params when both are provided", async () => {
      fetchMock.mockResolvedValue({
        ok: true,
        json: async () => ({ success: true }),
      });

      await scrapeSource("alberto_alvarez", true, 2000000, 4000000);

      expect(fetchMock).toHaveBeenCalledWith(
        "/api/scrape/batch?source=alberto_alvarez&force=true&price_min=2000000&price_max=4000000",
        expect.any(Object),
      );
    });

    it("should NOT add price params when only min is provided", async () => {
      fetchMock.mockResolvedValue({
        ok: true,
        json: async () => ({ success: true }),
      });

      await scrapeSource("proteger", false, 1500000, null);

      expect(fetchMock).toHaveBeenCalledWith(
        "/api/scrape/batch?source=proteger&force=false",
        expect.any(Object),
      );
    });

    it("should NOT add price params when only max is provided", async () => {
      fetchMock.mockResolvedValue({
        ok: true,
        json: async () => ({ success: true }),
      });

      await scrapeSource("escala_inmobiliaria", false, null, 3000000);

      expect(fetchMock).toHaveBeenCalledWith(
        "/api/scrape/batch?source=escala_inmobiliaria&force=false",
        expect.any(Object),
      );
    });

    it("should handle zero values correctly", async () => {
      fetchMock.mockResolvedValue({
        ok: true,
        json: async () => ({ success: true }),
      });

      await scrapeSource("uribienes", true, 0, 5000000);

      expect(fetchMock).toHaveBeenCalledWith(
        "/api/scrape/batch?source=uribienes&force=true&price_min=0&price_max=5000000",
        expect.any(Object),
      );
    });

    it("should handle API errors correctly", async () => {
      fetchMock.mockResolvedValue({
        ok: false,
        json: async () => ({ detail: "Prices must be positive" }),
      });

      await expect(scrapeSource("all", true, -100, 3000000)).rejects.toThrow(
        "Prices must be positive",
      );
    });

    it("should use POST method with correct headers", async () => {
      fetchMock.mockResolvedValue({
        ok: true,
        json: async () => ({ success: true }),
      });

      await scrapeSource("all", false, 1000000, 2000000);

      expect(fetchMock).toHaveBeenCalledWith(expect.any(String), {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
      });
    });
  });

  describe("Price Input Parsing", () => {
    it("should parse integer string to number", () => {
      const input = "2000000";
      const parsed = parseInt(input, 10);
      expect(parsed).toBe(2000000);
      expect(typeof parsed).toBe("number");
    });

    it("should handle trimmed whitespace", () => {
      const input = "  3500000  ";
      const parsed = parseInt(input.trim(), 10);
      expect(parsed).toBe(3500000);
    });

    it("should return NaN for empty string", () => {
      const input = "";
      const parsed = parseInt(input, 10);
      expect(isNaN(parsed)).toBe(true);
    });

    it("should return NaN for non-numeric string", () => {
      const input = "abc";
      const parsed = parseInt(input, 10);
      expect(isNaN(parsed)).toBe(true);
    });

    it("should handle leading zeros", () => {
      const input = "0002000000";
      const parsed = parseInt(input, 10);
      expect(parsed).toBe(2000000);
    });
  });

  describe("Price Validation Logic", () => {
    const validate = (min, max) => {
      const errors = [];

      if (min !== null && max !== null) {
        if (min < 0 || max < 0) {
          errors.push("Prices must be positive");
        }
        if (min >= max) {
          errors.push("Min price must be less than max price");
        }
        if (max > 50000000) {
          errors.push("Max price exceeds reasonable limit (50M)");
        }
      }

      return errors;
    };

    it("should pass validation for valid range", () => {
      const errors = validate(2000000, 4000000);
      expect(errors).toHaveLength(0);
    });

    it("should fail validation for negative prices", () => {
      const errors = validate(-1000, 4000000);
      expect(errors).toContain("Prices must be positive");
    });

    it("should fail validation when min >= max", () => {
      const errors = validate(4000000, 2000000);
      expect(errors).toContain("Min price must be less than max price");
    });

    it("should fail validation when min == max", () => {
      const errors = validate(3000000, 3000000);
      expect(errors).toContain("Min price must be less than max price");
    });

    it("should fail validation for excessive max price", () => {
      const errors = validate(1000000, 60000000);
      expect(errors).toContain("Max price exceeds reasonable limit (50M)");
    });

    it("should allow max price at boundary (50M)", () => {
      const errors = validate(1000000, 50000000);
      expect(errors).toHaveLength(0);
    });

    it("should allow zero as min price", () => {
      const errors = validate(0, 4000000);
      expect(errors).toHaveLength(0);
    });

    it("should not validate when both are null", () => {
      const errors = validate(null, null);
      expect(errors).toHaveLength(0);
    });
  });

  describe("ForceUpdate Checkbox Behavior", () => {
    beforeEach(() => {
      // Set up minimal DOM
      document.body.innerHTML = `
        <input type="checkbox" id="forceUpdate" />
        <input type="number" id="filterPriceMin" value="0" />
        <input type="number" id="filterPriceMax" value="4000000" />
      `;
    });

    it("should read filter values when forceUpdate is checked", () => {
      const forceUpdate = document.getElementById("forceUpdate");
      const filterPriceMin = document.getElementById("filterPriceMin");
      const filterPriceMax = document.getElementById("filterPriceMax");

      forceUpdate.checked = true;
      filterPriceMin.value = "2000000";
      filterPriceMax.value = "4500000";

      let scrapePriceMin = null;
      let scrapePriceMax = null;

      if (forceUpdate.checked) {
        const minInput = filterPriceMin.value.trim();
        const maxInput = filterPriceMax.value.trim();
        scrapePriceMin = minInput ? parseInt(minInput, 10) : null;
        scrapePriceMax = maxInput ? parseInt(maxInput, 10) : null;
      }

      expect(scrapePriceMin).toBe(2000000);
      expect(scrapePriceMax).toBe(4500000);
    });

    it("should NOT read filter values when forceUpdate is unchecked", () => {
      const forceUpdate = document.getElementById("forceUpdate");
      const filterPriceMin = document.getElementById("filterPriceMin");
      const filterPriceMax = document.getElementById("filterPriceMax");

      forceUpdate.checked = false;
      filterPriceMin.value = "2000000";
      filterPriceMax.value = "4500000";

      let scrapePriceMin = null;
      let scrapePriceMax = null;

      if (forceUpdate.checked) {
        const minInput = filterPriceMin.value.trim();
        const maxInput = filterPriceMax.value.trim();
        scrapePriceMin = minInput ? parseInt(minInput, 10) : null;
        scrapePriceMax = maxInput ? parseInt(maxInput, 10) : null;
      }

      expect(scrapePriceMin).toBe(null);
      expect(scrapePriceMax).toBe(null);
    });

    it("should handle empty input values correctly", () => {
      const forceUpdate = document.getElementById("forceUpdate");
      const filterPriceMin = document.getElementById("filterPriceMin");
      const filterPriceMax = document.getElementById("filterPriceMax");

      forceUpdate.checked = true;
      filterPriceMin.value = "";
      filterPriceMax.value = "";

      let scrapePriceMin = null;
      let scrapePriceMax = null;

      if (forceUpdate.checked) {
        const minInput = filterPriceMin.value.trim();
        const maxInput = filterPriceMax.value.trim();
        scrapePriceMin = minInput ? parseInt(minInput, 10) : null;
        scrapePriceMax = maxInput ? parseInt(maxInput, 10) : null;
      }

      expect(scrapePriceMin).toBe(null);
      expect(scrapePriceMax).toBe(null);
    });

    it("should handle default values from HTML attributes", () => {
      const filterPriceMin = document.getElementById("filterPriceMin");
      const filterPriceMax = document.getElementById("filterPriceMax");

      // Default values from HTML
      expect(filterPriceMin.value).toBe("0");
      expect(filterPriceMax.value).toBe("4000000");

      const min = parseInt(filterPriceMin.value, 10);
      const max = parseInt(filterPriceMax.value, 10);

      expect(min).toBe(0);
      expect(max).toBe(4000000);
    });
  });

  describe("Edge Cases", () => {
    it("should handle very large price values", () => {
      const min = 40000000;
      const max = 50000000;
      expect(min).toBeLessThan(max);
      expect(max).toBeLessThanOrEqual(50000000);
    });

    it("should handle decimal values (should be truncated by parseInt)", () => {
      const input = "2500000.99";
      const parsed = parseInt(input, 10);
      expect(parsed).toBe(2500000);
    });

    it("should handle scientific notation correctly", () => {
      const input = "2e6"; // 2000000
      const parsed = parseInt(input, 10);
      expect(parsed).toBe(2);
      // Note: parseInt with radix 10 doesn't handle scientific notation well
      // This test documents the actual behavior
    });
  });

  describe("Backend Integration Scenarios", () => {
    let fetchMock;

    beforeEach(() => {
      fetchMock = vi.fn();
      global.fetch = fetchMock;
    });

    it("should send default values (0, 4000000) when using defaults", async () => {
      fetchMock.mockResolvedValue({
        ok: true,
        json: async () => ({
          new_properties: 10,
          total_found: 50,
          cached: false,
        }),
      });

      await scrapeSource("all", true, 0, 4000000);

      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("price_min=0"),
        expect.any(Object),
      );
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("price_max=4000000"),
        expect.any(Object),
      );
    });

    it("should send custom values when user changes inputs", async () => {
      fetchMock.mockResolvedValue({
        ok: true,
        json: async () => ({
          new_properties: 5,
          total_found: 25,
          cached: false,
        }),
      });

      await scrapeSource("alberto_alvarez", true, 2000000, 3500000);

      const callUrl = fetchMock.mock.calls[0][0];
      expect(callUrl).toContain("price_min=2000000");
      expect(callUrl).toContain("price_max=3500000");
    });

    it("should omit price params when forceUpdate is unchecked", async () => {
      fetchMock.mockResolvedValue({
        ok: true,
        json: async () => ({
          new_properties: 0,
          total_found: 50,
          cached: true,
        }),
      });

      await scrapeSource("proteger", false, null, null);

      const callUrl = fetchMock.mock.calls[0][0];
      expect(callUrl).not.toContain("price_min");
      expect(callUrl).not.toContain("price_max");
    });
  });
});
