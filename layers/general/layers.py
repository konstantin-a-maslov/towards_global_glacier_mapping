import tensorflow as tf


class Residual(tf.keras.layers.Layer):
    def __init__(self, layer):
        super(Residual, self).__init__()
        self.layer = layer
    
    def call(self, x):
        x1 = self.layer(x)
        y = tf.math.add(x, x1)
        return y


class ResidualWithProjection(tf.keras.layers.Layer):
    def __init__(self, layer, projected_size):
        super(ResidualWithProjection, self).__init__()
        self.layer = layer
        self.projected_size = projected_size
        self.projection = tf.keras.layers.Dense(projected_size, use_bias=False)
    
    def call(self, x):
        x1 = self.layer(x)
        x = self.projection(x)
        y = tf.math.add(x, x1)
        return y


class ConvBatchNormAct(tf.keras.layers.Layer):
    def __init__(
        self, n_filters, kernel_size=3, dilation_rate=1, use_bias=True, padding="same", 
        activation=tf.keras.layers.LeakyReLU, spatial_dropout=0, inference_dropout=False
    ):
        super(ConvBatchNormAct, self).__init__()
        self.conv = tf.keras.layers.Conv2D(
            n_filters, 
            kernel_size, 
            dilation_rate=dilation_rate, 
            use_bias=use_bias,
            padding=padding
        )
        self.bn = tf.keras.layers.BatchNormalization()
        self.act = activation()
        self.spatial_dropout = spatial_dropout
        if spatial_dropout:
            self.dropout = tf.keras.layers.SpatialDropout2D(spatial_dropout)
            self.inference_dropout = inference_dropout

    def call(self, x):
        y = self.conv(x)
        y = self.bn(y)
        y = self.act(y)
        if self.spatial_dropout:
            y = self.dropout(y, training=self.inference_dropout)
        return y


class SeparableConvBatchNormAct(tf.keras.layers.Layer):
    def __init__(
        self, n_filters, kernel_size=3, dilation_rate=1, use_bias=True, padding="same", 
        activation=tf.keras.layers.LeakyReLU, spatial_dropout=0, inference_dropout=False
    ):
        super(SeparableConvBatchNormAct, self).__init__()
        self.conv = tf.keras.layers.SeparableConv2D(
            n_filters, 
            kernel_size, 
            dilation_rate=dilation_rate, 
            use_bias=use_bias,
            padding=padding
        )
        self.bn = tf.keras.layers.BatchNormalization()
        self.act = activation()
        self.spatial_dropout = spatial_dropout
        if spatial_dropout:
            self.dropout = tf.keras.layers.SpatialDropout2D(spatial_dropout)
            self.inference_dropout = inference_dropout

    def call(self, x):
        y = self.conv(x)
        y = self.bn(y)
        y = self.act(y)
        if self.spatial_dropout:
            y = self.dropout(y, training=self.inference_dropout)
        return y


class ConvBatchNormAct_x2(tf.keras.layers.Layer):
    def __init__(
        self, n_filters, kernel_size=3, dilation_rate=1, use_bias=True, padding="same", 
        activation=tf.nn.leaky_relu, spatial_dropout=0, inference_dropout=False
    ):
        super(ConvBatchNormAct_x2, self).__init__()
        self.conv1 = tf.keras.layers.Conv2D(
            n_filters, 
            kernel_size, 
            dilation_rate=dilation_rate, 
            use_bias=use_bias,
            padding=padding
        )
        self.bn1 = tf.keras.layers.BatchNormalization()
        self.act1 = activation
        self.conv2 = tf.keras.layers.Conv2D(
            n_filters, 
            kernel_size, 
            dilation_rate=dilation_rate, 
            use_bias=use_bias,
            padding=padding
        )
        self.bn2 = tf.keras.layers.BatchNormalization()
        self.act2 = activation
        self.spatial_dropout = spatial_dropout
        if spatial_dropout:
            self.dropout = tf.keras.layers.SpatialDropout2D(spatial_dropout)
            self.inference_dropout = inference_dropout

    def call(self, x):
        y = self.conv1(x)
        y = self.bn1(y)
        y = self.act1(y)
        y = self.conv2(y)
        y = self.bn2(y)
        y = self.act2(y)
        if self.spatial_dropout:
            y = self.dropout(y, training=self.inference_dropout)
        return y


class UpConv(tf.keras.layers.Layer):
    def __init__(
        self, n_filters, kernel_size=2, dilation_rate=1, use_bias=False, padding="same"
    ):
        super(UpConv, self).__init__()
        self.upsampling = tf.keras.layers.UpSampling2D(
            size=(kernel_size, kernel_size)
        )
        self.conv = tf.keras.layers.Conv2D(
            n_filters, 
            kernel_size, 
            dilation_rate=dilation_rate, 
            use_bias=use_bias,
            padding=padding
        )
        self.bn = tf.keras.layers.BatchNormalization()

    def call(self, x):
        y = self.upsampling(x)
        y = self.conv(y)
        y = self.bn(y)
        return y


class FusionBlock(tf.keras.layers.Layer):
    def __init__(
        self, n_filters, activation=tf.nn.leaky_relu, spatial_dropout=0, inference_dropout=False
    ):
        super(FusionBlock, self).__init__()
        self.n_filters = n_filters
        self.activation = activation
        self.spatial_dropout = spatial_dropout
        self.inference_dropout = inference_dropout

    def build(self, input_shape):
        self.conv_branches = []
        self.excitation_pools = []
        self.excitation_denses1 = []
        self.excitation_denses2 = []

        for _ in input_shape:
            self.conv_branches.append(
                ConvBatchNormAct_x2(
                    self.n_filters,
                    activation=self.activation,
                    spatial_dropout=self.spatial_dropout,
                    inference_dropout=self.inference_dropout
                )
            )
            self.excitation_pools.append(
                tf.keras.layers.GlobalAveragePooling2D(keepdims=True)
            )
            self.excitation_denses1.append(
                tf.keras.layers.Dense(self.n_filters, activation=self.activation)
            )
            self.excitation_denses2.append(
                tf.keras.layers.Dense(self.n_filters, activation=tf.nn.sigmoid)
            )

    def call(self, xs):
        outputs = []
        for x, conv, pool, dense1, dense2 in zip(
            xs, self.conv_branches, self.excitation_pools, self.excitation_denses1, 
            self.excitation_denses2
        ):
            _conv = conv(x)
            _pool = pool(_conv)
            _dense1 = dense1(_pool)
            _dense2 = dense2(_dense1)
            outputs.append(_conv * _dense2)
        y = tf.math.add_n(outputs)
        return y


class ConvBatchNormAct_series(tf.keras.layers.Layer):
    def __init__(
        self, n_filters_list, kernel_size=3, dilation_rate=1, use_bias=True, padding="same", 
        activation=tf.keras.layers.LeakyReLU, spatial_dropout=0, inference_dropout=False
    ):
        super(ConvBatchNormAct_series, self).__init__()
        self.convs = []
        self.bns = []
        self.acts = []
        for n_filters in n_filters_list:
            self.convs.append(tf.keras.layers.Conv2D(
                n_filters, 
                kernel_size, 
                dilation_rate=dilation_rate, 
                use_bias=use_bias,
                padding=padding
            ))
            self.bns.append(tf.keras.layers.BatchNormalization())
            self.acts.append(activation())
        self.spatial_dropout = spatial_dropout
        if spatial_dropout:
            self.dropout = tf.keras.layers.SpatialDropout2D(spatial_dropout)
            self.inference_dropout = inference_dropout

    def call(self, x):
        y = x
        for conv, bn, act in zip(self.convs, self.bns, self.acts):
            y = conv(y)
            y = bn(y)
            y = act(y)
        if self.spatial_dropout:
            y = self.dropout(y, training=self.inference_dropout)
        return y


class LocationEncodingBlock(tf.keras.layers.Layer):
    def __init__(
        self, n_units, activation=tf.keras.layers.LeakyReLU, dropout=0, inference_dropout=False
    ):
        super(LocationEncodingBlock, self).__init__()
        self.dense1 = tf.keras.layers.Dense(n_units)
        self.bn1 = tf.keras.layers.BatchNormalization()
        self.act1 = activation()
        self.dense2 = tf.keras.layers.Dense(n_units)
        self.bn2 = tf.keras.layers.BatchNormalization()
        self.act2 = activation()
        self.dropout_rate = dropout
        if dropout:
            self.dropout = tf.keras.layers.Dropout(dropout)
            self.inference_dropout = inference_dropout

    def call(self, x):
        y = self.dense1(x)
        y = self.bn1(y)
        y = self.act1(y)
        y = self.dense2(y)
        y = self.bn2(y)
        y = self.act2(y)
        if self.dropout_rate:
            y = self.dropout(y, training=self.inference_dropout)
        return y
