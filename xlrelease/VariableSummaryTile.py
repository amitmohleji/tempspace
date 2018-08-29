datalist = []

for item in release.variables:
    if item.key in variables:
        entry = {item.label:item.value}
        datalist.append(entry)
data = datalist