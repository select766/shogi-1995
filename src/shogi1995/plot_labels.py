"""Place numbered plot annotations deterministically without changing measured data."""


def spread_labels(figure,annotations):
    # Call only after axes limits, margins and subplot layout are final.
    figure.canvas.draw()
    renderer=figure.canvas.get_renderer()
    occupied={};offsets=[]
    candidates=[]
    for level in range(24):
        for vertical in (6+14*level,-14-14*level):
            for horizontal in (6,-18):candidates.append((horizontal,vertical))
    for annotation in annotations:
        axis=annotation.axes;bounds=axis.get_window_extent(renderer)
        previous=occupied.setdefault(axis,[])
        for offset in candidates:
            annotation.set_position(offset)
            box=annotation.get_window_extent(renderer).padded(2)
            if (bounds.x0<=box.x0 and box.x1<=bounds.x1
                    and bounds.y0<=box.y0 and box.y1<=bounds.y1
                    and not any(box.overlaps(other) for other in previous)):
                previous.append(box);offsets.append(list(offset));break
        else:raise ValueError('numbered measurement labels do not fit; increase the panel size')
    return offsets
