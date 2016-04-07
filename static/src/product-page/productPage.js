angular.module('productPage', [
    'ngRoute',
    'person'
])



    .config(function($routeProvider) {
        $routeProvider.when('/u/:orcid/doi/:id*/:filter?', {
            templateUrl: 'product-page/product-page.tpl.html',
            controller: 'productPageCtrl'
            ,
            resolve: {
                personResp: function($http, $route, Person){
                    console.log("loaded the person response in the route def")
                    return Person.load($route.current.params.orcid)
                }
            }
        })
    })



    .controller("productPageCtrl", function($scope,
                                           $routeParams,
                                           $route,
                                           $http,
                                           $mdDialog,
                                           $location,
                                           Person,
                                           personResp){


        var possibleChannels = _.pluck(Person.d.sources, "source_name")
        console.log("possibleChannels", possibleChannels, $routeParams.filter)
        var doi
        if (_.contains(possibleChannels, $routeParams.filter)) {
            // do filter stuff. this is not just part of the DOI
            console.log("we have a real filter", $routeParams.filter)
            doi = $routeParams.id
        }
        else {
            // crazy hack! this is how we are dealing with there
            // being slashes in the DOI.
            doi = $routeParams.id + "/" + $routeParams.filter
            console.log("no real filter. making the doi", doi)
        }

        var product = _.findWhere(Person.d.products, {doi: doi})

        $scope.person = Person.d
        $scope.sources = product.sources
        $scope.doi = doi
        $scope.product = product
        $scope.d = {}

        console.log("$scope.product", $scope.product, $routeParams.filter)




        function makePostsWithRollups(posts){
            var sortedPosts = _.sortBy(posts, "posted_on")
            var postsWithRollups = []
            function makeRollupPost(){
                return {
                    source: 'tweetRollup',
                    posted_on: '',
                    count: 0,
                    tweets: []
                }
            }
            var currentRollup = makeRollupPost()
            _.each(sortedPosts, function(post){
                if (post.source == 'twitter'){

                    // we keep tweets as regular posts too
                    postsWithRollups.push(post)

                    // put the tweet in the rollup
                    currentRollup.tweets.push(post)

                    // rollup posted_on date will be date of *first* tweet in group
                    if (!currentRollup.posted_on){
                        currentRollup.posted_on = post.posted_on
                    }
                }
                else {
                    postsWithRollups.push(post)

                    // save the current rollup
                    if (currentRollup.tweets.length){
                        postsWithRollups.push(currentRollup)
                    }

                    // clear the current rollup
                    currentRollup = makeRollupPost()
                }
            })

            // there may be rollup still sitting around because no regular post at end
            if (currentRollup.tweets.length){
                postsWithRollups.push(currentRollup)
            }
            return postsWithRollups
        }

        $scope.posts = makePostsWithRollups(product.posts)
        $scope.postsFilter = function(post){
            if ($scope.selectedChannel) {
                return post.source == $scope.selectedChannel.source_name
            }
            else { // we are trying to show unfiltered view

                // but even in unfiltered view we want to hide tweets.
                return post.source != 'twitter'

            }
        }

        $scope.postsSum = 0
        _.each($scope.sources, function(v){
            $scope.postsSum += v.posts_count
        })

        $scope.d.postsLimit = 20
        $scope.selectedChannel = _.findWhere(Person.d.sources, {source_name: $routeParams.filter})

        $scope.toggleSelectedChannel = function(channel){
            console.log("toggling selected channel", channel)
            var rootUrl = "u/" + Person.d.orcid_id + "/doi/" + doi
            if (channel.source_name == $routeParams.filter){
                $location.url(rootUrl)
            }
            else {
                $location.url(rootUrl + "/" + channel.source_name)
            }
        }




    })



