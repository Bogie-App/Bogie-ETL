from typing import Iterator

from models.station import Line, Station, StationLine, StationTiming


def _to_domain(rows) -> list[StationLine]:
    """Convertit un DataFrame de lignes canoniques en objets domaine StationLine."""
    result: list[StationLine] = []
    for row in rows.itertuples(index=False):
        result.append(
            StationLine(
                station=Station(
                    stop_id=row.stop_id,
                    name=row.stop_name,
                    description=row.stop_desc if row.stop_desc else None,
                    latitude=row.stop_lat,
                    longitude=row.stop_lon,
                ),
                line=Line(name=row.route_short_name),
                stop_sequence=int(row.stop_sequence_num),
            )
        )
    return result

def _to_timing_chunks(df, chunk_size: int = 10_000) -> Iterator[list[StationTiming]]:
    chunk: list[StationTiming] = []
    for row in df.itertuples(index=False):
        chunk.append(
            StationTiming(
                stop_id=row.stop_id,
                line_name=row.route_short_name,
                arrival_time=row.arrival_time_norm,
                departure_time=row.departure_time_norm,
                date=row.date_shifted,
                direction=int(row.direction_id),
            )
        )
        if len(chunk) >= chunk_size:
            yield chunk
            chunk = []

    if chunk:
        yield chunk