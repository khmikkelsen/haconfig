class Colour:
    def __init__(self,
                hue,
                sat,
                val=100,
                trans_max=3,
                trans_min=1,
                hs_dev=180,
                sat_dev=180,
                val_dev=0) -> None:
        self.hue = hue
        self.sat = sat
        self.val = val
        self.trans_max = trans_max
        self.trans_min = trans_min
        self.hs_dev = hs_dev
        self.sat_dev = sat_dev
        self.val_dev = val_dev

    def __str__(self) -> str:
        return f"Colour:hs:{self.hs}, sat: {self.sat}, val: {self.val}, trans_max: {self.trans_max}, trans_min: {self.trans_min}"