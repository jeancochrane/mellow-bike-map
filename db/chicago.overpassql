[out:xml][timeout:300][maxsize:1073741824]
[bbox:41.6229,-87.8558,42.0488,-87.5085];

(
  way["highway"];
  way["bicycle"];
  way["cycleway"];
  way["route"="bicycle"];
  rel["route"="bicycle"];
);
// Recurse down to include the nodes of ways and the members of relations
(._;>;);
out;
