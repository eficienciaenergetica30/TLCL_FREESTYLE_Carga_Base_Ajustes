entity TempRep4CFE {
        Division      : String; //DIVISION
    key Rpu           : String;
        Name          : String; //NOMBRE
        Address       : String; //DIRECCION
        Population    : String; //POBLACION
        Fare          : String; //TARIFA
    key FromDate      : String; //DESDE
    key ToDate        : String; //HASTA
    key BillDate      : String; //FECHA DE FACTURACION
        Consumption   : Decimal; //CONSUMO
        Demand        : Decimal; //DEMANDA
        ReactivePower : Decimal; //REACTIVOS
        PowerFactor   : Decimal; //FACTOR POTENCIA
        LoadFactor    : Decimal; //FACTOR CARGA
        Energy        : Decimal; //ENERGIA
        Iva           : Decimal;
        Dap           : Decimal;
        Charges       : Decimal; //CARGOS Y DEPOSITOS
        Credits       : Decimal; //CREDITOS Y REDONDEOS
        Total         : Decimal; //TOTAL
        Validation    : Decimal; //FORMULA VALIDACION
        Difference    : Decimal; //DIFERENCIA
    key IvaType       : String(4); //TIPO DE IVA (T16,T8N,T8S)
}