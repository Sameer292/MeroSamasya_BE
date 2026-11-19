# Nepal report boundaries

`nepal_report_boundaries.geojsonl.gz` contains one GeoJSON feature per line
with WGS84 polygons for the 753 local levels in `nepal_locations.json`.
Feature IDs come from the source
dataset. Each feature lists the current district and local-level names first,
followed by the equivalent pair from the earlier English seed where available.
The API resolves these names to IDs in the running database.

The geometry comes from YoungInnovations' high-resolution Nepal local-level
dataset. It combines Ministry of Federal Affairs and Local Development and
Open Knowledge Nepal boundary data. This copy excludes standalone protected
areas, repairs polygon topology, combines multipart records, rounds coordinates
to six decimal places, and maps current and historical names. Pins outside
the included polygons have no municipality match.

- [YoungInnovations source at 7424450, published under the MIT License](https://github.com/younginnovations/nepal-locallevel-map/tree/74244508ca4e1a1f37593b76f3b3e64dceeb0a01)
- [Open Knowledge Nepal LocalBoundaries, licensed under CC BY 4.0](https://localboundries.oknp.org/about/)
- [CC BY 4.0 license](https://creativecommons.org/licenses/by/4.0/)

## YoungInnovations MIT License

Copyright (c) 2019 YoungInnovations

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
