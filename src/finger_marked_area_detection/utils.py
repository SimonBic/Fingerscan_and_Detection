def generator_bis_ende(generator):
    #Treibt einen Generator bis zum Ende durch und gibt dessen
    try:
        while True:
            next(generator)
    except StopIteration as e:
        return e.value
 