import { describe, it, expect } from "vitest";
import { filterProperties, sortProperties } from "../modules/filters.js";

// Mock utils since filters imports them.
// Vitest automocking works, but since we are using native modules, integration testing might be easier.
// However, since we are using imports in the source file like `/static/utils.js`, running this in Node tests might fail
// because Node doesn't know how to resolve `/static/`.
// We need to validte if we need to mock import paths or setup module resolution in vitest config.
// For now, let's write the test assuming we might need to fix import paths or use a vitest alias.

describe("Filters", () => {
  const mockProperties = [
    {
      id: 1,
      price: "1000",
      area: "50",
      bedrooms: 2,
      parking: 1,
      source: "generic",
      location: "Barrio A",
      created_at: "2023-01-01",
    },
    {
      id: 2,
      price: "2000",
      area: "100",
      bedrooms: 3,
      parking: 2,
      source: "specific",
      location: "Barrio B",
      created_at: "2023-01-02",
    },
    {
      id: 3,
      price: "500",
      area: "20",
      bedrooms: 1,
      parking: 0,
      source: "generic",
      location: "Barrio A",
      created_at: "2023-01-03",
    },
  ];

  describe("filterProperties", () => {
    it("should filter by price range", () => {
      const result = filterProperties(mockProperties, { priceMin: 1500 });
      expect(result).toHaveLength(1);
      expect(result[0].id).toBe(2);
    });

    it("should filter by area range", () => {
      const result = filterProperties(mockProperties, { areaMax: 60 });
      expect(result).toHaveLength(2); // 50 and 20
    });

    it("should filter by bedrooms", () => {
      const result = filterProperties(mockProperties, { bedsMin: 2 });
      expect(result).toHaveLength(2); // id 1 and 2
    });

    it("should filter by specific source", () => {
      const result = filterProperties(mockProperties, {
        selectedWebsite: "specific",
      });
      expect(result).toHaveLength(1);
      expect(result[0].id).toBe(2);
    });

    it("should filter by Barrio", () => {
      const result = filterProperties(mockProperties, {
        selectedBarrios: ["Barrio A"],
      });
      expect(result).toHaveLength(2);
    });

    it("should return all if filters are empty", () => {
      const result = filterProperties(mockProperties, {});
      expect(result).toHaveLength(3);
    });
  });

  describe("sortProperties", () => {
    it("should sort by price asc", () => {
      const result = sortProperties(mockProperties, "price_asc");
      expect(result[0].id).toBe(3); // 500
      expect(result[1].id).toBe(1); // 1000
      expect(result[2].id).toBe(2); // 2000
    });

    it("should sort by price desc", () => {
      const result = sortProperties(mockProperties, "price_desc");
      expect(result[0].id).toBe(2);
    });

    it("should sort by area desc", () => {
      const result = sortProperties(mockProperties, "area_desc");
      expect(result[0].id).toBe(2); // 100
    });

    it("should sort by created_at desc (default)", () => {
      const result = sortProperties(mockProperties, "created_desc");
      expect(result[0].id).toBe(3); // newest
    });
  });
});
