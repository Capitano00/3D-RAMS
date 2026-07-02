import assert from "node:assert/strict";
import { sceneModeFrom } from "./sceneContext.js";

function badgeValues(context) {
  return Object.fromEntries(context.badges.map((badge) => [badge.label, badge.value]));
}

{
  const context = sceneModeFrom(
    {
      scene: { dataMode: "cached-public-fixture", provider: "cesium-local-cached-fixture", featureCount: 4 },
      location: { dataMode: "cached-public-fixture", sourceIds: ["public-lambeth-planning-context"] },
      sources: [
        { id: "public-lambeth-planning-context", status: "cached-public" },
        { id: "public-ea-flood-context", status: "cached-public" },
      ],
    },
    {},
    null,
  );
  const badges = badgeValues(context);

  assert.equal(context.label, "Cached fixture");
  assert.equal(context.tone, "cached");
  assert.equal(badges.Sources, "2 sources");
  assert.equal(badges.Features, "4 features");
}

{
  const context = sceneModeFrom(
    {
      scene: { dataMode: "synthetic-fixture", provider: "cesium-local-fixture", featureCount: 1 },
      runtime: {
        planningData: {
          status: "disabled",
          dataMode: "disabled",
          fallbackReason: "ENABLE_LIVE_PLANNING_DATA is not true.",
        },
      },
      trace: [
        {
          name: "load_geospatial_features",
          status: "fallback",
          fallbackReason: "Fallback used after simulated live map provider failure for demo testing.",
        },
      ],
    },
    {},
    null,
  );
  const badges = badgeValues(context);

  assert.equal(context.label, "Fallback");
  assert.equal(context.tone, "fallback");
  assert.equal(badges.Planning, "Disabled");
  assert.match(badges.Fallback, /simulated live map provider failure/);
}

{
  const context = sceneModeFrom(
    {
      scene: { dataMode: "synthetic-fixture", provider: "cesium-local-fixture", featureCount: 2 },
      runtime: {
        planningData: {
          status: "live",
          dataMode: "live-planning-data",
          featureCount: 1,
          sourceIds: ["planning-data-api"],
          freshness: "2026-07-02",
        },
      },
    },
    {},
    null,
    {
      intake: {
        locationCandidate: {
          label: "8 Albert Embankment",
          source: "Postcodes.io",
          sourceId: "postcodes-io",
          dataMode: "live-postcode-candidate",
        },
      },
    },
  );
  const badges = badgeValues(context);

  assert.equal(badges.Planning, "Live");
  assert.equal(badges.Location, "Postcodes.io");
  assert.equal(badges.Sources, "2 sources");
  assert.equal(badges.Freshness, "2026-07-02");
}
